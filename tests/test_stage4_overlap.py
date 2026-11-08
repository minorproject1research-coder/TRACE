"""Stage 4 overlapped with Stage 3 (STAGE4_OVERLAP) and the parallel Stage 3 preparation (STAGE3_PREP_WORKERS). Offline: fakes only."""
import threading
import time
from types import SimpleNamespace

import pytest

from apps.api.graph.nodes import factcheck_node as node
from apps.api.graph.nodes import summarizer_node as sn
from apps.api.services import progress

QID = "q-overlap"
_real_discard = node.discard                      # tests replace node.discard; the fixture must still clean up


@pytest.fixture
def seen():
    events = []
    progress.register(QID, events.append)
    yield events
    progress.unregister(QID)
    _real_discard(QID)


def sqs(n=3):
    return [SimpleNamespace(id=f"s{i}", main_topic=f"Topic {i}?", detail_questions=["d"]) for i in range(1, n + 1)]


def fake_check(calls=None, fail=(), delay=0.0, tracker=None):
    def check(query_id, sq, report):
        if tracker is not None:
            with tracker["lock"]:
                tracker["running"] += 1
                tracker["max"] = max(tracker["max"], tracker["running"])
        try:
            report("claims", f"reading {sq.id}", sources=1)
            time.sleep(delay)
            if calls is not None:
                calls.append(sq.id)
            if sq.id in fail:
                raise RuntimeError("model error")
            report("conflicts", f"conflicts {sq.id}")
            return [{"label": "supported", "claim": f"c-{sq.id}", "contested": False}], [{"d": sq.id}], {"supported": 1, "disagreements": 1}
        finally:
            if tracker is not None:
                with tracker["lock"]:
                    tracker["running"] -= 1
    return check


# -------------------------------------------------------------------------------------------------- the registry in factcheck_node
def test_collect_returns_none_when_nothing_was_started_early():
    assert node.collect("nobody", sqs()) is None
    assert not node.overlap_started("nobody")


def test_early_jobs_run_on_one_worker_and_results_keep_the_sub_question_order(monkeypatch, seen):
    tracker = {"lock": threading.Lock(), "running": 0, "max": 0}
    calls = []
    monkeypatch.setattr(node, "_check_sub_question", fake_check(calls, delay=0.05, tracker=tracker))
    subs = sqs(3)
    for i, sq in enumerate(subs, 1):
        assert node.start_in_background(QID, sq, i, 3) is True
    assert node.overlap_started(QID)
    results = node.collect(QID, subs)
    assert [r[2] for r in results] == [{"supported": 1, "disagreements": 1}] * 3
    assert [r[0][0]["claim"] for r in results] == ["c-s1", "c-s2", "c-s3"]
    assert calls == ["s1", "s2", "s3"] and tracker["max"] == 1               # one Stage 4 sub-question at a time
    assert not node.overlap_started(QID)                                    # collected: the registry is clean


def test_a_sub_question_that_was_not_started_early_is_checked_by_collect_and_errors_stay_per_sub_question(monkeypatch, seen):
    calls = []
    monkeypatch.setattr(node, "_check_sub_question", fake_check(calls, fail=("s1",)))
    subs = sqs(3)
    node.start_in_background(QID, subs[0], 1, 3)
    node.start_in_background(QID, subs[2], 3, 3)                           # s2 was never queued (its start failed)
    results = node.collect(QID, subs)
    assert "RuntimeError" in results[0][2]["error"] and results[0][0] == []
    assert results[1][2]["supported"] == 1 and results[1][0][0]["claim"] == "c-s2"
    assert results[2][2]["supported"] == 1
    assert sorted(calls) == ["s1", "s2", "s3"]


def test_starting_the_same_sub_question_twice_queues_it_once(monkeypatch, seen):
    calls = []
    monkeypatch.setattr(node, "_check_sub_question", fake_check(calls))
    sq = sqs(1)[0]
    assert node.start_in_background(QID, sq, 1, 1) and node.start_in_background(QID, sq, 1, 1)
    node.collect(QID, [sq])
    assert calls == ["s1"]


def test_start_in_background_never_raises(monkeypatch):
    def broken():
        raise RuntimeError("cannot schedule new futures after interpreter shutdown")
    monkeypatch.setattr(node, "_executor", broken)
    try:
        assert node.start_in_background("q-broken", sqs(1)[0], 1, 1) is False
    finally:
        node.discard("q-broken")


def test_discard_cancels_jobs_that_have_not_started(monkeypatch, seen):
    gate = threading.Event()
    calls = []

    def check(query_id, sq, report):
        gate.wait(5)
        calls.append(sq.id)
        return [], [], {}
    monkeypatch.setattr(node, "_check_sub_question", check)
    subs = sqs(3)
    for i, sq in enumerate(subs, 1):
        node.start_in_background(QID, sq, i, 3)
    time.sleep(0.1)                                                          # s1 is running (blocked on the gate), s2 and s3 wait in the queue
    node.discard(QID)
    gate.set()
    time.sleep(0.2)
    assert calls == ["s1"] and not node.overlap_started(QID)


def test_progress_is_held_back_until_the_factcheck_node_starts_then_replayed_in_order_and_live(monkeypatch, seen):
    monkeypatch.setattr(node, "_check_sub_question", fake_check())
    subs = sqs(2)
    node.start_in_background(QID, subs[0], 1, 2)
    for _ in range(100):                                                     # wait until the worker has finished s1
        if node._overlaps[QID].futures["s1"].done():
            break
        time.sleep(0.01)
    assert [e for e in seen if e["lane"] == "factcheck"] == []              # nothing visible while Stage 3 "runs"
    node.activate(QID)
    replay = [(e["step"], e["data"]["subQuestion"], e["data"]["subQuestions"]) for e in seen if e["lane"] == "factcheck"]
    assert replay == [("claims", 1, 2), ("conflicts", 1, 2)]
    node.start_in_background(QID, subs[1], 2, 2)
    node.collect(QID, subs)
    steps = [(e["step"], e["data"]["subQuestion"]) for e in seen if e["lane"] == "factcheck"]
    assert steps == [("claims", 1), ("conflicts", 1), ("claims", 2), ("conflicts", 2)]          # live after activate, order kept


def test_run_factcheck_uses_the_early_results_and_writes_like_before(monkeypatch, seen):
    monkeypatch.setattr(node, "_check_sub_question", fake_check(fail=("s2",)))
    written = {}
    monkeypatch.setattr(node.db_service, "write_fact_claims", lambda q, rows: written.update(claims=rows))
    monkeypatch.setattr(node.db_service, "write_contradictions", lambda q, rows: written.update(contra=rows))
    subs = sqs(3)
    for i, sq in enumerate(subs, 1):
        node.start_in_background(QID, sq, i, 3)
    claims, summary = node.run_factcheck(QID, subs)
    assert [c["claim"] for c in claims] == ["c-s1", "c-s3"]
    assert list(summary) == ["s1", "s2", "s3"] and "RuntimeError" in summary["s2"]["error"]
    assert written == {"claims": claims, "contra": [{"d": "s1"}, {"d": "s3"}]}


def test_factcheck_node_with_early_jobs_gives_the_same_state_and_the_stage_events_in_order(monkeypatch, seen):
    monkeypatch.setenv("FACTCHECK", "true")
    monkeypatch.setattr(node, "_check_sub_question", fake_check())
    monkeypatch.setattr(node.db_service, "write_fact_claims", lambda q, rows: None)
    monkeypatch.setattr(node.db_service, "write_contradictions", lambda q, rows: None)
    subs = sqs(2)
    for i, sq in enumerate(subs, 1):
        node.start_in_background(QID, sq, i, 2)
    out = node.factcheck_node(SimpleNamespace(task_plan=SimpleNamespace(query_id=QID, sub_questions=subs)))
    assert len(out["fact_claims"]) == 2 and set(out["fact_summary"]) == {"s1", "s2"}
    order = [(e["step"], e["state"]) for e in seen if e["lane"] == "factcheck"]
    assert order[0] == ("branch", "running") and order[-1] == ("store", "completed")      # the node's own start, then everything, then the end
    assert order.count(("branch", "running")) == 1 and order.count(("store", "completed")) == 1
    assert not node.overlap_started(QID)


def test_factcheck_node_without_early_jobs_is_the_old_sequential_path(monkeypatch, seen):
    monkeypatch.setenv("FACTCHECK", "true")
    calls = []
    monkeypatch.setattr(node, "_check_sub_question", fake_check(calls))
    monkeypatch.setattr(node.db_service, "write_fact_claims", lambda q, rows: None)
    monkeypatch.setattr(node.db_service, "write_contradictions", lambda q, rows: None)
    subs = sqs(2)
    out = node.factcheck_node(SimpleNamespace(task_plan=SimpleNamespace(query_id=QID, sub_questions=subs)))
    assert calls == ["s1", "s2"] and len(out["fact_claims"]) == 2
    assert [e["data"]["subQuestion"] for e in seen if e["step"] == "claims"] == [1, 2]


# ------------------------------------------------------------------------------------------------------- the summarizer
def patch_stage3(monkeypatch, n=3, prep_delay=0.0, prep_threads=None, barrier=None):
    sub_questions = sqs(n)

    def flatten(details, sq_id, topic):
        if prep_threads is not None:
            prep_threads.add(threading.current_thread().name)
        time.sleep(prep_delay)
        if barrier is not None and threading.current_thread().name.startswith("stage3-prep"):
            barrier.wait(5)                                                      # passes only when all the sub-questions are being prepared at once
        return [f"a-{sq_id}"], {f"a-{sq_id}": "d"}
    monkeypatch.setattr(sn.detail_aspects, "flatten_aspects", flatten)
    monkeypatch.setattr(sn.detail_aspects, "with_topic_aspect", lambda a, m, d, t, enabled=None: (a + ["t"], m, d))
    monkeypatch.setattr(sn.detail_aspects, "merge_mode", lambda: "x")
    monkeypatch.setattr(sn.db_service, "get_papers_for_stage3", lambda qid, sq_id: [{"id": f"{sq_id}-p{i}", "title": "P", "combined_score": 0.8, "has_full_text": True} for i in range(2)])
    monkeypatch.setattr(sn.db_service, "get_web_sources_for_stage3", lambda sq_id: [{"id": f"{sq_id}-w", "title": "W", "snippet": "x" * 300, "reliability_score": 0.4}])
    monkeypatch.setattr(sn.chunk_selector, "build_chunks", lambda p: [])
    monkeypatch.setattr(sn.chunk_selector, "select_chunks", lambda *a, **k: [(0, "text")])
    monkeypatch.setattr(sn.digest_generator, "generate_digest", lambda *a, **k: [{"claim": "c", "quote": "q", "verified": True, "stance": "supports"}])
    monkeypatch.setattr(sn.evidence_judge, "run_judge_for_subquestion", lambda aspects, rows, lookup, **kw: ([], {}))
    monkeypatch.setattr(sn.coverage_check, "check_coverage_judged", lambda *a, **k: {"sufficient": True, "judge_used": True, "judge_stats": {}, "uncovered_aspects": []})
    monkeypatch.setattr(sn, "_workers", lambda: 2)
    return SimpleNamespace(task_plan=SimpleNamespace(query_id=QID, sub_questions=sub_questions, domain_anchor="", domain_context=""))


def record_writes(monkeypatch, log):
    monkeypatch.setattr(sn.db_service, "write_digests", lambda rows: log.append(("digests", sorted({r["sub_question_id"] for r in rows}), len(rows))))
    monkeypatch.setattr(sn.db_service, "write_coverage", lambda rows: log.append(("coverage", [r["sub_question_id"] for r in rows], len(rows))))


def test_overlap_stores_each_sub_question_when_it_is_finished_then_queues_stage_4(monkeypatch, seen):
    monkeypatch.setenv("FACTCHECK", "true")
    node.expect(QID)                                                             # the planner of a graph run announces the query
    state = patch_stage3(monkeypatch)
    log = []
    record_writes(monkeypatch, log)
    monkeypatch.setattr(node, "start_in_background", lambda qid, sq, index, total: log.append(("start", sq.id, index, total)) or True)
    monkeypatch.setattr(node, "discard", lambda qid, keep_expected=False: log.append(("discard", qid)))
    out = sn.summarizer_node(state)
    assert len(out["digests"]) == 9 and set(out["coverage"]) == {"s1", "s2", "s3"}
    assert log == [("discard", QID),
                   ("digests", ["s1"], 3), ("coverage", ["s1"], 1), ("start", "s1", 1, 3),
                   ("digests", ["s2"], 3), ("coverage", ["s2"], 1), ("start", "s2", 2, 3),
                   ("digests", ["s3"], 3), ("coverage", ["s3"], 1), ("start", "s3", 3, 3)]      # no second, final write
    order = [(r["step"], r["state"]) for r in seen if r["lane"] == "summarizer"]
    assert order.index(("judge", "completed")) < order.index(("store", "completed"))


def test_without_overlap_everything_is_written_once_at_the_end_and_stage_4_is_not_queued(monkeypatch, seen):
    monkeypatch.setenv("FACTCHECK", "true")
    monkeypatch.setenv("STAGE4_OVERLAP", "false")
    state = patch_stage3(monkeypatch)
    log = []
    record_writes(monkeypatch, log)
    monkeypatch.setattr(node, "start_in_background", lambda *a: pytest.fail("Stage 4 must not start early"))
    monkeypatch.setattr(node, "discard", lambda *a: pytest.fail("no overlap, nothing to discard"))
    sn.summarizer_node(state)
    assert log == [("digests", ["s1", "s2", "s3"], 9), ("coverage", ["s1", "s2", "s3"], 3)]


def test_with_factcheck_off_the_overlap_switch_changes_nothing(monkeypatch, seen):
    monkeypatch.setenv("STAGE4_OVERLAP", "true")                                 # FACTCHECK is off (conftest)
    state = patch_stage3(monkeypatch)
    log = []
    record_writes(monkeypatch, log)
    monkeypatch.setattr(node, "start_in_background", lambda *a: pytest.fail("Stage 4 is off"))
    sn.summarizer_node(state)
    assert log == [("digests", ["s1", "s2", "s3"], 9), ("coverage", ["s1", "s2", "s3"], 3)]


def test_a_stage_4_start_that_fails_never_breaks_the_summarizer(monkeypatch, seen):
    monkeypatch.setenv("FACTCHECK", "true")
    node.expect(QID)
    state = patch_stage3(monkeypatch, n=2)
    log = []
    record_writes(monkeypatch, log)

    def explode(*a):
        raise RuntimeError("cannot queue")
    monkeypatch.setattr(node, "start_in_background", explode)
    monkeypatch.setattr(node, "discard", lambda qid, keep_expected=False: None)
    out = sn.summarizer_node(state)
    assert len(out["digests"]) == 6 and [x[0] for x in log] == ["digests", "coverage", "digests", "coverage"]


def test_a_failed_write_fails_the_node_as_before_and_cancels_the_queued_jobs(monkeypatch, seen):
    monkeypatch.setenv("FACTCHECK", "true")
    node.expect(QID)
    state = patch_stage3(monkeypatch, n=2)
    discards = []
    monkeypatch.setattr(node, "discard", lambda qid, keep_expected=False: discards.append(qid))
    monkeypatch.setattr(node, "start_in_background", lambda *a: True)
    monkeypatch.setattr(sn.db_service, "write_digests", lambda rows: (_ for _ in ()).throw(ConnectionError("database down")))
    monkeypatch.setattr(sn.db_service, "write_coverage", lambda rows: None)
    with pytest.raises(ConnectionError):
        sn.summarizer_node(state)
    assert discards == [QID, QID]                                                # once at the start, once because Stage 3 failed


def test_parallel_preparation_gives_the_same_jobs_in_the_same_order(monkeypatch, seen):
    state = patch_stage3(monkeypatch, n=4)
    # the two runs must see identical job lists: capture them through the digest step
    def jobs_of(workers):
        monkeypatch.setenv("STAGE3_PREP_WORKERS", str(workers))
        captured = []
        original = sn.digest_generator.generate_digest_with_retry

        def spy(topic, selected, **kw):
            captured.append((topic, kw["cache_scope"]))
            return [], 0
        monkeypatch.setattr(sn.digest_generator, "generate_digest_with_retry", spy)
        monkeypatch.setattr(sn, "_workers", lambda: 1)                           # one digest worker: the call order is the jobs order
        monkeypatch.setattr(sn.db_service, "write_digests", lambda rows: None)
        monkeypatch.setattr(sn.db_service, "write_coverage", lambda rows: None)
        sn.summarizer_node(state)
        monkeypatch.setattr(sn.digest_generator, "generate_digest_with_retry", original)
        return captured
    sequential, parallel = jobs_of(1), jobs_of(4)
    assert len(sequential) == 12 and sequential == parallel
    assert [c[1][0] for c in sequential] == ["s1"] * 3 + ["s2"] * 3 + ["s3"] * 3 + ["s4"] * 3


def test_preparation_runs_sub_questions_side_by_side_and_one_by_one_when_asked(monkeypatch, seen):
    monkeypatch.setattr(sn.db_service, "write_digests", lambda rows: None)
    monkeypatch.setattr(sn.db_service, "write_coverage", lambda rows: None)
    threads = set()
    state = patch_stage3(monkeypatch, n=4, prep_threads=threads, barrier=threading.Barrier(4))
    monkeypatch.setenv("STAGE3_PREP_WORKERS", "4")
    sn.summarizer_node(state)
    prep = {t for t in threads if t != "MainThread" and not t.startswith("stage3-sq")}                              # step 3 asks for the aspects again (cached) from the main thread
    assert len(prep) > 1 and all(t.startswith("stage3-prep") for t in prep)
    assert len(prep) == 4
    threads.clear()
    monkeypatch.setenv("STAGE3_PREP_WORKERS", "1")
    sn.summarizer_node(state)
    assert not any(t.startswith("stage3-prep") for t in threads)


def test_prep_workers_setting_is_forgiving(monkeypatch):
    monkeypatch.delenv("STAGE3_PREP_WORKERS", raising=False)
    assert sn._prep_workers() == 4
    monkeypatch.setenv("STAGE3_PREP_WORKERS", "0")
    assert sn._prep_workers() == 1
    monkeypatch.setenv("STAGE3_PREP_WORKERS", "many")
    assert sn._prep_workers() == 4


# ------------------------------------------------------------------------------------------------- the shared embedding model
def test_the_shared_embedder_serialises_encode():
    from apps.api.agents.stage2_retrieval.relevance_filter import _SerializedEmbedder
    state = {"running": 0, "max": 0}
    lock = threading.Lock()

    class Model:
        dim = 7

        def encode(self, texts, **kw):
            with lock:
                state["running"] += 1
                state["max"] = max(state["max"], state["running"])
            time.sleep(0.02)
            with lock:
                state["running"] -= 1
            return texts
    emb = _SerializedEmbedder(Model())
    threads = [threading.Thread(target=emb.encode, args=(["x"],), kwargs={"normalize_embeddings": True}) for _ in range(5)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert state["max"] == 1 and emb.dim == 7                                      # other attributes pass through


def test_a_direct_call_of_the_summarizer_without_the_planner_queues_no_stage_4_jobs(monkeypatch, seen):
    """The dev scripts (run_stage3_judge.py, the audits) call summarizer_node directly: nothing would collect early Stage 4 jobs, and
    they would spend Groq calls for nothing."""
    monkeypatch.setenv("FACTCHECK", "true")
    node.discard(QID)                                                            # not announced by a planner
    state = patch_stage3(monkeypatch)
    log = []
    record_writes(monkeypatch, log)
    monkeypatch.setattr(node, "start_in_background", lambda *a: pytest.fail("no planner, no early Stage 4"))
    sn.summarizer_node(state)
    assert log == [("digests", ["s1", "s2", "s3"], 9), ("coverage", ["s1", "s2", "s3"], 3)]      # the old single write at the end


def test_discard_stops_a_running_job_at_its_next_step_and_a_queued_one_never_starts(monkeypatch):
    import threading
    started, release, steps = threading.Event(), threading.Event(), []

    def check(query_id, sq, report):
        report("claims", "x")
        steps.append((sq.id, "claims"))
        started.set()
        release.wait(5)
        report("clusters", "y")                                                  # the step boundary where a discarded job must stop
        steps.append((sq.id, "clusters"))
        return [], [], {}
    monkeypatch.setattr(node, "_check_sub_question", check)
    subs = sqs(2)
    node.start_in_background("q-cancel", subs[0], 1, 2)
    node.start_in_background("q-cancel", subs[1], 2, 2)
    assert started.wait(5)
    node.discard("q-cancel")
    release.set()
    res = node._executor().submit(lambda: None)
    res.result(5)                                                                # the single worker has finished the cancelled job
    assert steps == [("s1", "claims")]                                           # s1 stopped before "clusters"; s2 was cancelled in the queue
