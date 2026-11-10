"""Telemetry for the timeline (2026-11-10): the run's Groq use on live events, notes (progress.note), one event per parsed paper, cache-hit counts.
Offline: fakes only, no network, no models."""
import asyncio
import collections
import time
from types import SimpleNamespace

import pytest

from apps.api.graph.nodes import paper_retrieval_node as prn
from apps.api.services import cache_counters, groq_pool, progress, run_manager as rm

QID = "22222222-2222-2222-2222-222222222222"


@pytest.fixture
def seen():
    got = []
    progress.register(QID, got.append)
    yield got
    progress.unregister(QID)


# ------------------------------------------------------------------------------------------------------------------------ Groq use
def test_the_meter_counts_the_seconds_keys_were_parked():
    snap = groq_pool.meter.snapshot()
    groq_pool.meter.rate_limited("gsk_abcdEFGH", "digest", 12.4)
    groq_pool.meter.rate_limited("gsk_abcdEFGH", "digest", 30)
    used = groq_pool.meter.since(snap)
    assert used["totals"]["rate_limited"] == 2 and used["totals"]["parked_seconds"] == 42


def test_the_run_record_reports_its_groq_use_so_far_and_can_be_switched_off(monkeypatch):
    rec = rm.RunRecord("r1", "q")
    assert rec.groq() is None                                           # not started
    rec.usage_before = groq_pool.meter.snapshot()
    groq_pool.meter.rate_limited("gsk_abcdEFGH", "stage4_near", 20)
    g = rec.groq(by_purpose=True)
    assert g["rateLimits"] == 1 and g["parkedSeconds"] == 20 and g["tokens"] == 0 and "byPurpose" in g
    assert "byPurpose" not in rec.groq()
    monkeypatch.setenv("RUN_TELEMETRY", "false")
    assert rec.groq() is None


class NotesGraph:
    def stream(self, state, stream_mode):
        qid = state.query_id
        yield {"planner": {"task_plan": SimpleNamespace(sub_questions=[], domain_anchor=None)}}
        progress.note(qid, "s2_skipped", "Semantic Scholar was skipped", level="warn", stage="retrieval")
        progress.report(qid, "papers", "paper_parse", "completed", "parsed: T", paperId="p1", outcome="parsed", chars=5000)
        yield {"paper_retrieval": {"paper_results": []}}
        yield {"web_search": {"web_sources": []}}
        yield {"summarizer": {"digests": [], "coverage": {}}}


def test_notes_and_step_events_carry_the_stage_and_the_groq_use():
    manager = rm.RunManager(graph_factory=lambda: NotesGraph(), max_workers=1, max_pending=1)
    try:
        rec = manager.submit("How do things work?")
        deadline = time.time() + 5
        while not rec.finished and time.time() < deadline:
            time.sleep(0.05)
        ev = rec.events_from(0)
        note = next(e for e in ev if e["event"] == "step" and e["data"].get("step") == "s2_skipped")
        assert note["stage"] == "retrieval" and note["data"]["lane"] == "notes" and note["data"]["level"] == "warn" and note["data"]["state"] == "completed"
        paper = next(e for e in ev if e["data"].get("step") == "paper_parse")
        assert paper["data"]["outcome"] == "parsed" and paper["stage"] == "retrieval"
        for e in (note, paper):
            assert set(e["data"]["groq"]) == {"tokens", "calls", "rateLimits", "parkedSeconds"}
        completed = [e for e in ev if e["event"] == "stage_completed"]
        assert completed and all("groq" in e["data"] and "byPurpose" in e["data"]["groq"] for e in completed)
        started = [e for e in ev if e["event"] == "stage_started"]
        assert started and all("byPurpose" not in e["data"]["groq"] for e in started)
        done = ev[-1]
        assert done["event"] == "run_completed" and {"groqTokens", "groqCalls", "groqRateLimits", "groqParkedSeconds"} <= set(done["data"])
    finally:
        manager.shutdown()


def test_a_note_never_breaks_the_caller(seen):
    progress.note(None, "x", "nothing")                                 # no run id
    progress.note("not-registered", "x", "nothing")
    progress.note(QID, "plan_cache", "The stored plan was reused", stage="planner", source="plan-cache")
    assert seen == [{"lane": "notes", "step": "plan_cache", "state": "completed", "message": "The stored plan was reused",
                     "data": {"level": "info", "stage": "planner", "source": "plan-cache"}}]


# ----------------------------------------------------------------------------------------------------------------- per-paper parse events
class FakeAgent:
    def __init__(self, outcomes):
        self._o = outcomes

    def parse_outcome(self, paper_id):
        return self._o[paper_id]


def test_each_parsed_paper_gets_an_event_with_its_outcome_route_and_reason(seen):
    agent = FakeAgent({"a": {"chars": 90000, "route": "own link", "reason": None}, "b": {"chars": 400, "route": None, "reason": None},
                       "c": {"chars": 0, "route": None, "reason": "HTTP 403"}, "d": {"chars": 50000, "route": "parse cache", "reason": None}})
    rows = {k: {"id": k, "title": f"Title {k}", "sub_question_id": "s1"} for k in "abcd"}
    warmed = []
    warmer = SimpleNamespace(submit=warmed.append)
    tally, reasons = collections.Counter(), collections.Counter()
    done = prn._paper_done_callback(agent, QID, rows, warmer, tally, reasons)
    for pid in "abcd":
        done(pid)
    events = [r for r in seen if r["step"] == "paper_parse"]
    assert [(e["data"]["paperId"], e["data"]["outcome"], e["data"]["route"], e["data"]["reason"]) for e in events] == [
        ("a", "parsed", "own link", None), ("b", "abstract_only", None, None), ("c", "failed", None, "HTTP 403"), ("d", "parsed", "parse cache", None)]
    assert all(e["lane"] == "papers" and e["state"] == "completed" and e["data"]["subQuestionId"] == "s1" for e in events)
    assert warmed == list("abcd")                                       # every paper is also handed to the chunk warm-up
    assert tally["parsed"] == 2 and tally["abstract_only"] == 1 and tally["failed"] == 1 and tally["fromParseCache"] == 1 and reasons == {"HTTP 403": 1}


def test_the_callback_survives_an_agent_without_outcomes_and_a_broken_event(seen):
    warmed = []
    done = prn._paper_done_callback(object(), QID, {}, SimpleNamespace(submit=warmed.append), collections.Counter(), collections.Counter())
    done("x")                                                           # no parse_outcome: an abstract-only paper with no reason
    assert warmed == ["x"] and seen[-1]["data"]["outcome"] == "abstract_only"


def test_the_parse_notes_summarise_the_outcomes_and_the_warm_up(seen):
    tally = collections.Counter(parsed=20, abstract_only=2, failed=1, fromParseCache=3)
    prn._parse_notes(QID, 24, tally, collections.Counter({"HTTP 403": 1}), SimpleNamespace(enabled=True, papers=20, chunks=700))
    notes = {r["step"]: r for r in seen if r["lane"] == "notes"}
    s = notes["parse_summary"]
    assert s["data"]["level"] == "warn" and s["data"]["parsed"] == 20 and s["data"]["abstractOnly"] == 2 and s["data"]["failed"] == 1 and s["data"]["reasons"] == {"HTTP 403": 1}
    assert "20 of 24" in s["message"] and "3 from the parse cache" in s["message"] and "HTTP 403: 1" in s["message"]
    assert notes["chunk_warmup"]["data"] == {"level": "info", "stage": "retrieval", "papers": 20, "chunks": 700}
    seen.clear()
    prn._parse_notes(QID, 5, collections.Counter(parsed=5), collections.Counter(), SimpleNamespace(enabled=False, papers=0, chunks=0))
    assert [r["step"] for r in seen] == ["parse_summary"] and seen[0]["data"]["level"] == "info"


# ------------------------------------------------------------------------------------------------------------------- cache counters
def test_the_cache_counters_count_by_name_and_are_read_as_differences():
    base = cache_counters.get("digest")
    cache_counters.bump("digest")
    cache_counters.bump("digest", 4)
    assert cache_counters.get("digest") - base == 5 and cache_counters.get("never-used") == 0
