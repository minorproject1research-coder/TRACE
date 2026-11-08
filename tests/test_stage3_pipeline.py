"""Stage 3 pipeline: a sub-question is judged as soon as its own digests are done (STAGE3_PIPELINE) and several sub-questions are judged at the
same time (STAGE3_SQ_WORKERS). Offline: fakes only, no network, no models."""
import threading
import time
from types import SimpleNamespace

import pytest

from apps.api.agents.stage3_summarizer import evidence_judge
from apps.api.graph.nodes import factcheck_node as node
from apps.api.graph.nodes import summarizer_node as sn
from apps.api.services import progress

QID = "q-pipeline"


def sqs(n):
    return [SimpleNamespace(id=f"s{i}", main_topic=f"Topic {i}?", detail_questions=["d"]) for i in range(1, n + 1)]


@pytest.fixture
def seen():
    events = []
    progress.register(QID, events.append)
    yield events
    progress.unregister(QID)
    node.discard(QID)


def patch(monkeypatch, n=3, digest_wait=None, judge=None):
    """digest_wait(topic) -> called inside every digest call of that sub-question; judge(sq_topic_aspects) -> called inside the judge."""
    monkeypatch.setattr(sn.detail_aspects, "flatten_aspects", lambda details, sq_id, topic: ([f"a-{sq_id}"], {f"a-{sq_id}": "d"}))
    monkeypatch.setattr(sn.detail_aspects, "with_topic_aspect", lambda a, m, d, t, enabled=None: (a + ["t"], m, d))
    monkeypatch.setattr(sn.detail_aspects, "merge_mode", lambda: "x")
    monkeypatch.setattr(sn.db_service, "get_papers_for_stage3", lambda qid, sq_id: [{"id": f"{sq_id}-p{i}", "title": "P", "combined_score": 0.8, "has_full_text": True} for i in range(2)])
    monkeypatch.setattr(sn.db_service, "get_web_sources_for_stage3", lambda sq_id: [])
    monkeypatch.setattr(sn.chunk_selector, "build_chunks", lambda p: [])
    monkeypatch.setattr(sn.chunk_selector, "select_chunks", lambda *a, **k: [(0, "text")])

    def digest(sub_question, selected, **kw):
        if digest_wait:
            digest_wait(sub_question)
        return [{"claim": "c", "quote": "q", "verified": True, "stance": "supports"}]
    monkeypatch.setattr(sn.digest_generator, "generate_digest", digest)

    def run_judge(aspects, rows, lookup, **kw):
        if judge:
            judge(aspects[0])
        return [], {}
    monkeypatch.setattr(sn.evidence_judge, "run_judge_for_subquestion", run_judge)
    monkeypatch.setattr(sn.coverage_check, "check_coverage_judged", lambda *a, **k: {"sufficient": True, "judge_used": True, "judge_stats": {}, "uncovered_aspects": []})
    monkeypatch.setattr(sn.db_service, "write_digests", lambda rows: None)
    monkeypatch.setattr(sn.db_service, "write_coverage", lambda rows: None)
    monkeypatch.setattr(sn, "_workers", lambda: 4)
    monkeypatch.setenv("STAGE3_PREP_WORKERS", "1")
    return SimpleNamespace(task_plan=SimpleNamespace(query_id=QID, sub_questions=sqs(n), domain_anchor="", domain_context=""))


def test_a_sub_question_is_judged_while_the_digests_of_a_later_one_are_still_running(monkeypatch, seen):
    first_judged = threading.Event()

    def digest_wait(topic):
        if topic == "Topic 3?":                                            # the last sub-question's digests only finish after sub-question 1 was judged
            assert first_judged.wait(5), "sub-question 1 was not judged while sub-question 3 was still reading"
    state = patch(monkeypatch, digest_wait=digest_wait, judge=lambda aspect: first_judged.set() if aspect == "a-s1" else None)
    monkeypatch.setenv("STAGE3_PIPELINE", "true")
    out = sn.summarizer_node(state)
    assert first_judged.is_set() and len(out["digests"]) == 6


def test_with_the_pipeline_off_every_digest_comes_before_the_first_judge(monkeypatch, seen):
    order = []
    state = patch(monkeypatch, digest_wait=lambda topic: order.append(("digest", topic)), judge=lambda aspect: order.append(("judge", aspect)))
    monkeypatch.setenv("STAGE3_PIPELINE", "false")
    sn.summarizer_node(state)
    kinds = [k for k, _ in order]
    assert kinds.index("judge") == kinds.count("digest")                    # all 6 digest calls came first


def test_two_sub_questions_are_judged_at_the_same_time_and_one_by_one_when_asked(monkeypatch, seen):
    barrier = threading.Barrier(2)
    reached = []

    def judge(aspect):
        try:
            barrier.wait(1.0)                                              # passes only if another sub-question is in the judge at the same moment
            reached.append("together")
        except threading.BrokenBarrierError:
            barrier.reset()
            reached.append("alone")
    state = patch(monkeypatch, n=2, judge=judge)
    monkeypatch.setenv("STAGE3_SQ_WORKERS", "2")
    sn.summarizer_node(state)
    assert reached == ["together", "together"]
    reached.clear()
    monkeypatch.setenv("STAGE3_SQ_WORKERS", "1")
    sn.summarizer_node(state)
    assert reached == ["alone", "alone"]


def test_the_result_is_in_the_original_order_whatever_finishes_first(monkeypatch, seen):
    def judge(aspect):
        time.sleep({"a-s1": 0.3, "a-s2": 0.1, "a-s3": 0.0}[aspect])      # sub-question 3 is judged first, 1 last
    state = patch(monkeypatch, judge=judge)
    monkeypatch.setenv("STAGE3_SQ_WORKERS", "3")
    out = sn.summarizer_node(state)
    assert list(out["coverage"]) == ["s1", "s2", "s3"]
    assert [d["sub_question_id"] for d in out["digests"]] == ["s1", "s1", "s2", "s2", "s3", "s3"]


def test_judge_events_never_precede_the_end_of_the_digest_step_and_the_counts_are_right(monkeypatch, seen):
    state = patch(monkeypatch)
    monkeypatch.setenv("STAGE3_SQ_WORKERS", "2")
    sn.summarizer_node(state)
    lane = [(e["step"], e["state"]) for e in seen if e["lane"] == "summarizer"]
    assert lane.index(("digest", "completed")) < min(i for i, x in enumerate(lane) if x[0] == "judge")
    judged = [e for e in seen if e["lane"] == "summarizer" and e["step"] == "judge" and e["message"].startswith("Judged sub-question")]
    assert sorted(e["data"]["done"] for e in judged) == [1, 2, 3] and judged[-1]["data"]["sufficientSoFar"] == 3
    assert lane[-1] == ("store", "completed")


def test_when_one_sub_question_fails_the_others_write_and_queue_nothing_afterwards(monkeypatch, seen):
    monkeypatch.setenv("FACTCHECK", "true")
    node.expect(QID)
    failed = threading.Event()
    writes, starts = [], []

    def judge(aspect):
        if aspect == "a-s1":
            failed.set()
            raise ValueError("judge host down")
        failed.wait(2)
        time.sleep(0.5)                                                    # long enough for the node to see the failure and set the abort flag
    state = patch(monkeypatch, judge=judge)
    monkeypatch.setattr(sn.db_service, "write_digests", lambda rows: writes.append("digests"))
    monkeypatch.setattr(sn.db_service, "write_coverage", lambda rows: writes.append("coverage"))
    monkeypatch.setattr(node, "start_in_background", lambda *a: starts.append(a) or True)
    monkeypatch.setenv("STAGE3_SQ_WORKERS", "3")
    with pytest.raises(ValueError, match="judge host down"):
        sn.summarizer_node(state)
    assert writes == [] and starts == []


def test_the_judge_cache_keeps_the_verdicts_of_two_calls_that_saved_one_after_the_other():
    a, b = {"key-a": {"v": 1}}, {"key-b": {"v": 2}}                       # both loaded the same (empty) file before judging
    evidence_judge._save_judge_cache(a)
    evidence_judge._save_judge_cache(b)
    assert set(evidence_judge._load_judge_cache()) == {"key-a", "key-b"}


def test_the_judge_cache_survives_many_threads_saving_at_once():
    def save(i):
        evidence_judge._save_judge_cache({f"k{i}": {"v": i}})
    threads = [threading.Thread(target=save, args=(i,)) for i in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert set(evidence_judge._load_judge_cache()) == {f"k{i}" for i in range(12)}


def test_workers_and_pipeline_settings_are_forgiving(monkeypatch):
    monkeypatch.delenv("STAGE3_SQ_WORKERS", raising=False)
    assert sn._sq_workers() == 2
    monkeypatch.setenv("STAGE3_SQ_WORKERS", "0")
    assert sn._sq_workers() == 1
    monkeypatch.setenv("STAGE3_SQ_WORKERS", "x")
    assert sn._sq_workers() == 2
    monkeypatch.delenv("STAGE3_PIPELINE", raising=False)
    assert sn._pipeline_enabled() is True
    monkeypatch.setenv("STAGE3_PIPELINE", "off")
    assert sn._pipeline_enabled() is False
