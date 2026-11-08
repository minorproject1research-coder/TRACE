"""Offline tests: the relevance filter of paper_retrieval_node runs the sub-questions in parallel (RELEVANCE_WORKERS) and the
result is the same as one after the other. No network, no models: filter_relevant, the agent and the database are fakes."""
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from apps.api.graph.nodes import paper_retrieval_node as prn  # noqa: E402
from apps.api.services import progress  # noqa: E402

QID = "q-relevance-parallel"
N_SQ = 5
BACKENDS = {0: "server", 1: "server", 2: "groq", 3: "server", 4: "none"}


class FakeAgent:
    """Every sub-question 'finds' 6 papers; the sub-question named 'BAD*' raises like a failed search."""
    def __init__(self, max_results_per_query=10):
        pass

    async def retrieve(self, sub_question, query_variants, enrich):
        if sub_question.startswith("BAD"):
            raise RuntimeError("search exploded")
        return [{"title": f"{sub_question} paper {i}"} for i in range(6)]

    async def enrich_papers(self, papers):
        return papers

    async def parse_papers(self, paper_ids):
        return []


def make_filter(delays=None, calls=None):
    """Fake filter_relevant: keeps papers 0..k-1 where k depends on the sub-question; sleeps `delays[topic]` seconds."""
    delays = delays or {}

    def fake_filter(sub_question, papers, anchor="", context="", stats=None):
        idx = int(sub_question.split("-")[-1])
        if calls is not None:
            calls.append((sub_question, threading.current_thread().name, anchor, context))
        time.sleep(delays.get(sub_question, 0))
        kept = papers[: idx + 1]
        stats.update(candidates=len(papers), shortlisted=idx + 3, judged=idx + 2, passed=len(kept), judgeUnavailable=idx % 2,
                     backend=BACKENDS[idx])
        return kept
    return fake_filter


def setup_node(monkeypatch, workers, fake_filter, topics=None):
    monkeypatch.setattr(prn, "PaperRetrievalAgent", FakeAgent)
    monkeypatch.setattr(prn.relevance_filter, "filter_relevant", fake_filter)
    monkeypatch.setattr(prn.relevance_filter, "compute_combined_score", lambda p: {**p, "combined_score": 0.5})
    monkeypatch.setattr(prn.reliability_scorer, "score_all", lambda ps: ps)
    monkeypatch.setattr(prn.db_service, "write_retrieved_papers", lambda qid, ps: None)
    monkeypatch.setattr(prn, "_parse_relevant_papers", _no_parse)
    if workers is None:
        monkeypatch.delenv("RELEVANCE_WORKERS", raising=False)
    else:
        monkeypatch.setenv("RELEVANCE_WORKERS", str(workers))
    events = []
    monkeypatch.setattr(progress, "report", lambda run_id, lane, step, state="running", message="", **data:
                        events.append({"lane": lane, "step": step, "state": state, "message": message, "data": data}))
    topics = topics or [f"topic-{i}" for i in range(N_SQ)]
    sqs = [SimpleNamespace(id=f"s{i}", main_topic=t, queries=["q"], papers=[]) for i, t in enumerate(topics)]
    state = SimpleNamespace(task_plan=SimpleNamespace(query_id=QID, sub_questions=sqs, domain_anchor="ANCHOR", domain_context="CTX"))
    return state, events


async def _no_parse(*a, **k):
    return None


def run(monkeypatch, workers, delays=None, topics=None, calls=None):
    state, events = setup_node(monkeypatch, workers, make_filter(delays, calls), topics)
    out = prn.paper_retrieval_node(state)
    return state, out, events


def snapshot(state, out, events):
    """What must not depend on the number of workers."""
    sqs = state.task_plan.sub_questions
    final = next(e for e in events if e["step"] == "relevance_filter" and e["state"] == "completed")
    return {
        "per_sq": [[p["title"] for p in sq.papers] for sq in sqs],
        "all": [p["title"] for p in out["paper_results"]],
        "sq_ids": [[p["sub_question_id"] for p in sq.papers] for sq in sqs],
        "final": (final["message"], final["data"]),
    }


def test_same_result_for_one_and_many_workers_even_when_the_last_finishes_first(monkeypatch):
    # sub-question 0 is the slowest, so with several workers they finish in the reverse order
    delays = {"topic-0": 0.30, "topic-1": 0.20, "topic-2": 0.10, "topic-3": 0.0, "topic-4": 0.0}
    base = snapshot(*run(monkeypatch, 1, delays))
    for workers in (2, 4, 16):
        assert snapshot(*run(monkeypatch, workers, delays)) == base
    # the base itself: the kept papers are the first idx+1 of each sub-question, in the sub-question order
    assert base["per_sq"] == [[f"topic-{i} paper {j}" for j in range(i + 1)] for i in range(N_SQ)]
    assert base["all"] == [t for sq in base["per_sq"] for t in sq]
    assert base["sq_ids"] == [[f"s{i}"] * (i + 1) for i in range(N_SQ)]


def test_totals_and_backend_are_summed_in_sub_question_order(monkeypatch):
    _, _, events = run(monkeypatch, 4, {"topic-4": 0.2, "topic-0": 0.0})      # the last one finishes last, then a different order
    final = next(e for e in events if e["step"] == "relevance_filter" and e["state"] == "completed")["data"]
    assert final["candidates"] == 6 * N_SQ
    assert final["shortlisted"] == sum(i + 3 for i in range(N_SQ))
    assert final["judged"] == sum(i + 2 for i in range(N_SQ))
    assert final["passed"] == sum(i + 1 for i in range(N_SQ))
    assert final["judgeUnavailable"] == sum(i % 2 for i in range(N_SQ))
    assert final["backend"] == "none"                                         # the backend of the LAST sub-question, as in the old loop
    # same when the last sub-question finishes first
    _, _, events = run(monkeypatch, 4, {"topic-0": 0.2, "topic-4": 0.0})
    assert next(e for e in events if e["step"] == "relevance_filter" and e["state"] == "completed")["data"]["backend"] == "none"


def test_sub_questions_really_overlap_and_one_worker_does_not(monkeypatch):
    delays = {f"topic-{i}": 0.15 for i in range(N_SQ)}
    t0 = time.perf_counter()
    run(monkeypatch, 1, delays)
    sequential = time.perf_counter() - t0
    t0 = time.perf_counter()
    calls = []
    run(monkeypatch, 5, delays, calls=calls)
    parallel = time.perf_counter() - t0
    assert sequential >= 5 * 0.15
    assert parallel < sequential * 0.75
    assert len({thread for _, thread, _, _ in calls}) > 1                     # worker threads were used
    # anchor and context reach every call unchanged
    assert {(a, c) for _, _, a, c in calls} == {("ANCHOR", "CTX")}


def test_one_worker_runs_in_the_calling_thread_in_order(monkeypatch):
    calls = []
    run(monkeypatch, 1, calls=calls)
    assert [c[0] for c in calls] == [f"topic-{i}" for i in range(N_SQ)]
    assert {c[1] for c in calls} == {threading.current_thread().name}


def test_a_failed_retrieval_is_isolated_and_handled_as_before(monkeypatch, caplog):
    topics = ["topic-0", "BAD-1", "topic-2", "topic-3", "BAD-4"]
    # BAD-* sub-questions never reach the filter, so the fake filter's index parsing only sees topic-0/2/3
    def fake_filter(sub_question, papers, anchor="", context="", stats=None):
        idx = int(sub_question.split("-")[-1])
        time.sleep(0.05 * (4 - idx))
        stats.update(candidates=len(papers), shortlisted=2, judged=2, passed=1, judgeUnavailable=0, backend="server")
        return papers[:1]

    results = {}
    for workers in (1, 4):
        state, events = setup_node(monkeypatch, workers, fake_filter, topics)
        for sq in state.task_plan.sub_questions:
            sq.papers = ["stale"]
        with caplog.at_level("ERROR", logger="apps.api.agents.stage2_retrieval"):
            caplog.clear()
            out = prn.paper_retrieval_node(state)
            errors = [r.getMessage() for r in caplog.records if "Retrieval failed" in r.getMessage()]
        sqs = state.task_plan.sub_questions
        assert sqs[1].papers == [] and sqs[4].papers == []
        assert [p["title"] for p in sqs[0].papers] == ["topic-0 paper 0"]
        assert [p["title"] for p in out["paper_results"]] == ["topic-0 paper 0", "topic-2 paper 0", "topic-3 paper 0"]
        assert errors == ["Retrieval failed for sub-question 'BAD-1': search exploded", "Retrieval failed for sub-question 'BAD-4': search exploded"]
        final = next(e for e in events if e["step"] == "relevance_filter" and e["state"] == "completed")["data"]
        assert final["candidates"] == 18 and final["passed"] == 3 and final["judged"] == 6
        running = [e for e in events if e["step"] == "relevance_filter" and e["state"] == "running" and "done" in e["data"]]
        assert all(e["data"]["total"] == 5 for e in running)
        assert len(running) == 4                                              # the opening event (done=0) and one per filtered sub-question
        results[workers] = ([[p["title"] for p in sq.papers] for sq in sqs], final)
    assert results[1] == results[4]


def test_all_retrievals_failed_does_not_start_a_pool(monkeypatch):
    state, events = setup_node(monkeypatch, 4, make_filter(), ["BAD-0", "BAD-1"])
    out = prn.paper_retrieval_node(state)
    assert out["paper_results"] == []
    assert all(sq.papers == [] for sq in state.task_plan.sub_questions)
    final = next(e for e in events if e["step"] == "relevance_filter" and e["state"] == "completed")["data"]
    assert final["passed"] == 0 and final["backend"] is None


def test_progress_events_keep_their_shape_and_count_finished_sub_questions(monkeypatch):
    delays = {"topic-0": 0.30, "topic-1": 0.20, "topic-2": 0.10, "topic-3": 0.0, "topic-4": 0.0}
    _, _, events = run(monkeypatch, 5, delays)
    rf = [e for e in events if e["step"] == "relevance_filter"]
    assert rf[0]["state"] == "running" and rf[0]["data"] == {"candidates": 30, "done": 0, "total": N_SQ}
    running = [e for e in rf if e["state"] == "running" and e["data"].get("done", 0) > 0]
    assert [e["data"]["done"] for e in running] == [1, 2, 3, 4, 5]            # counts finished sub-questions, never skips or repeats
    assert [e["message"] for e in running] == [f"Judged sub-question {i} of {N_SQ}" for i in range(1, 6)]
    keys = {"done", "total", "backend", "candidates", "shortlisted", "judged", "passed", "judgeUnavailable"}
    assert all(set(e["data"]) == keys for e in running)
    for field in ("candidates", "shortlisted", "judged", "passed", "judgeUnavailable"):
        series = [e["data"][field] for e in running]
        assert series == sorted(series)                                       # running totals only grow
    assert running[-1]["data"]["passed"] == sum(i + 1 for i in range(N_SQ))
    # the sub-questions finish in the order of their delays (3 and 4 first, 0 last), so the running totals follow completion order
    assert running[0]["data"]["passed"] in (4, 5)
    assert rf[-1]["state"] == "completed" and rf[-1]["message"] == f"{15} of 30 candidates passed (20 judge calls)"


def test_a_failure_inside_the_filter_still_propagates(monkeypatch):
    def broken(sub_question, papers, anchor="", context="", stats=None):
        if sub_question == "topic-2":
            raise ValueError("filter bug")
        stats.update(candidates=len(papers), shortlisted=1, judged=1, passed=1, judgeUnavailable=0, backend="server")
        return papers[:1]
    for workers in (1, 4):
        state, _ = setup_node(monkeypatch, workers, broken)
        with pytest.raises(ValueError, match="filter bug"):
            prn.paper_retrieval_node(state)


@pytest.mark.parametrize("value,expected", [(None, 2), ("1", 1), ("8", 8), ("0", 1), ("-3", 1), ("abc", 2)])
def test_relevance_workers_setting(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("RELEVANCE_WORKERS", raising=False)
    else:
        monkeypatch.setenv("RELEVANCE_WORKERS", value)
    assert prn._relevance_workers() == expected


# ------------------------------------------------------------------------------------------- thread safety of the embedder
def test_embedder_is_loaded_once_and_encode_is_never_concurrent(monkeypatch):
    import numpy as np
    from apps.api.agents.stage2_retrieval import relevance_filter as rf

    loads, active, overlaps = [], [0], [0]
    guard = threading.Lock()

    class FakeModel:
        def encode(self, texts, normalize_embeddings=True):
            with guard:
                active[0] += 1
                overlaps[0] = max(overlaps[0], active[0])
            time.sleep(0.02)
            with guard:
                active[0] -= 1
            return np.ones((len(texts), 3), dtype="float32")

    def fake_sentence_transformer(*a, **k):
        loads.append(1)
        time.sleep(0.05)                                   # a slow load: other threads arrive while it is running
        return FakeModel()

    monkeypatch.setattr(rf, "_embedder", None)
    monkeypatch.setattr(rf, "SentenceTransformer", fake_sentence_transformer)
    barrier = threading.Barrier(6)

    def work(i):
        barrier.wait()
        papers = [{"title": f"t{i}-{j}", "abstract": "a"} for j in range(3)]
        return len(rf.embedding_prefilter(f"question {i}", papers, top_k=20, min_similarity=0.5))

    with ThreadPoolExecutor(max_workers=6) as pool:
        counts = list(pool.map(work, range(6)))
    assert counts == [3] * 6
    assert len(loads) == 1                                 # the model was loaded once, not once per thread
    assert overlaps[0] == 1                                # encode() calls never overlapped
