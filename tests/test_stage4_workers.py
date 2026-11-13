"""STAGE4_SQ_WORKERS: how many sub-questions Stage 4 checks at the same time, and the per-job judge counters that stay exact when they overlap.
Offline: fakes only."""
import threading
import time
from types import SimpleNamespace

import pytest

from apps.api.agents.stage4_factcheck import judge
from apps.api.graph.nodes import factcheck_node as node
from apps.api.services import progress

QID = "q-workers"
_real_discard = node.discard


@pytest.fixture
def seen():
    events = []
    progress.register(QID, events.append)
    yield events
    progress.unregister(QID)
    _real_discard(QID)


def sqs(n):
    return [SimpleNamespace(id=f"s{i}", main_topic=f"Topic {i}?", detail_questions=["d"]) for i in range(1, n + 1)]


def tracked_check(tracker, delay=0.15):
    def check(query_id, sq, report):
        with tracker["lock"]:
            tracker["running"] += 1
            tracker["max"] = max(tracker["max"], tracker["running"])
        try:
            time.sleep(delay)
            return [{"label": "supported", "claim": f"c-{sq.id}", "contested": False}], [], {"supported": 1}
        finally:
            with tracker["lock"]:
                tracker["running"] -= 1
    return check


def run(monkeypatch, workers, n=4):
    monkeypatch.setenv("STAGE4_SQ_WORKERS", str(workers))
    tracker = {"lock": threading.Lock(), "running": 0, "max": 0}
    monkeypatch.setattr(node, "_check_sub_question", tracked_check(tracker))
    subs = sqs(n)
    for i, sq in enumerate(subs, 1):
        assert node.start_in_background(QID, sq, i, n)
    results = node.collect(QID, subs)
    return tracker, results


def test_the_default_is_two_sub_questions_and_one_when_set_to_one(monkeypatch, seen):
    monkeypatch.delenv("STAGE4_SQ_WORKERS", raising=False)
    assert node._sq_workers() == 2
    monkeypatch.setenv("STAGE4_SQ_WORKERS", "1")
    assert node._sq_workers() == 1
    tracker = {"lock": threading.Lock(), "running": 0, "max": 0}
    monkeypatch.setattr(node, "_check_sub_question", tracked_check(tracker, 0.05))
    subs = sqs(3)
    for i, sq in enumerate(subs, 1):
        node.start_in_background(QID, sq, i, 3)
    node.collect(QID, subs)
    assert tracker["max"] == 1


def test_two_workers_run_two_sub_questions_at_once_and_keep_the_order(monkeypatch, seen):
    tracker, results = run(monkeypatch, 2)
    assert tracker["max"] == 2
    assert [r[0][0]["claim"] for r in results] == ["c-s1", "c-s2", "c-s3", "c-s4"]


def test_the_pool_is_made_again_when_the_setting_changes(monkeypatch, seen):
    tracker, _ = run(monkeypatch, 1)
    assert tracker["max"] == 1
    tracker, _ = run(monkeypatch, 2)
    assert tracker["max"] == 2
    tracker, _ = run(monkeypatch, 1)
    assert tracker["max"] == 1


def test_the_setting_is_forgiving(monkeypatch):
    for raw, want in (("0", 1), ("-3", 1), ("x", 1), ("", 1), ("3", 3)):
        monkeypatch.setenv("STAGE4_SQ_WORKERS", raw)
        assert node._sq_workers() == want


def test_a_failing_sub_question_does_not_stop_the_other_worker(monkeypatch, seen):
    monkeypatch.setenv("STAGE4_SQ_WORKERS", "2")

    def check(query_id, sq, report):
        if sq.id == "s1":
            raise RuntimeError("model error")
        return [{"label": "supported", "claim": f"c-{sq.id}", "contested": False}], [], {}
    monkeypatch.setattr(node, "_check_sub_question", check)
    subs = sqs(3)
    for i, sq in enumerate(subs, 1):
        node.start_in_background(QID, sq, i, 3)
    results = node.collect(QID, subs)
    assert results[0][2]["error"].startswith("RuntimeError") and results[1][0] and results[2][0]


# ------------------------------------------------------------------------------------------------ per-job judge counters
def test_judge_counters_of_two_jobs_running_together_are_exact():
    barrier = threading.Barrier(2)
    out = {}

    def job(name, calls, hits, waits):
        with judge.track() as jt:
            barrier.wait(2)                                   # both jobs count at the same time
            for _ in range(calls):
                judge._bump("calls")
            for _ in range(hits):
                judge._bump("cache_hits")
            for _ in range(waits):
                judge._bump("waits")
            out[name] = dict(jt)
    before = judge.stats()
    threads = [threading.Thread(target=job, args=("a", 5, 2, 1)), threading.Thread(target=job, args=("b", 3, 7, 0))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert (out["a"]["calls"], out["a"]["cache_hits"], out["a"]["waits"]) == (5, 2, 1)
    assert (out["b"]["calls"], out["b"]["cache_hits"], out["b"]["waits"]) == (3, 7, 0)
    after = judge.stats()
    assert after["calls"] - before["calls"] == 8 and after["cache_hits"] - before["cache_hits"] == 9      # the global counters still add up


def test_judge_counters_follow_the_work_into_the_judge_threads(monkeypatch):
    monkeypatch.setenv("STAGE4_WORKERS", "4")
    with judge.track() as jt:
        judge.run_parallel(lambda i: judge._bump("failures"), [(i,) for i in range(6)])
    assert jt["failures"] == 6


def test_a_counter_outside_any_job_only_changes_the_global_counters():
    before = judge.stats()["calls"]
    judge._bump("calls")
    assert judge.stats()["calls"] == before + 1
