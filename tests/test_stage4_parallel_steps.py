"""The near-match judge (Groq) and the conflict NLI (CPU) of one sub-question run side by side; the NLI model preloads in the background."""
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from apps.api.agents.stage4_factcheck import common, contradiction_detector, fact_checker  # noqa: E402
from apps.api.graph.nodes import factcheck_node as node  # noqa: E402


def stub_everything_but_the_two_steps(monkeypatch):
    monkeypatch.setattr(node.db_service, "get_digests_for_stage4", lambda q, sq: [])
    monkeypatch.setattr(node.db_service, "get_missing_evidence", lambda sq: [])
    monkeypatch.setattr(fact_checker, "load_claims", lambda d: [])
    monkeypatch.setattr(fact_checker, "build_clusters", lambda c: [])
    monkeypatch.setattr(fact_checker, "verify_support", lambda c: c)
    monkeypatch.setattr(fact_checker, "label_clusters", lambda c, conflicts: [])


def run_once():
    return node._check_sub_question("q1", SimpleNamespace(id="s1", main_topic="topic"), lambda *a, **k: None)


def test_the_near_step_and_the_conflict_step_overlap(monkeypatch):
    stub_everything_but_the_two_steps(monkeypatch)
    monkeypatch.setattr(fact_checker, "NEAR_ON", True)
    monkeypatch.setenv("STAGE4_PARALLEL_STEPS", "true")
    near_started, threads = threading.Event(), {}

    def near(clusters):
        threads["near"] = threading.current_thread().name
        near_started.set()
        return clusters

    def detect(clusters):
        threads["detect"] = threading.current_thread().name
        assert near_started.wait(2.0), "the near step must run while the conflict step is running"
        return {}, []
    monkeypatch.setattr(fact_checker, "find_near_matches", near)
    monkeypatch.setattr(contradiction_detector, "detect", detect)
    labeled, disagreements, summary = run_once()
    assert threads["near"] != threads["detect"] and threads["near"].startswith("stage4-near")
    assert labeled == [] and summary["total"] == 0


def test_sequential_when_switched_off(monkeypatch):
    stub_everything_but_the_two_steps(monkeypatch)
    monkeypatch.setattr(fact_checker, "NEAR_ON", True)
    monkeypatch.setenv("STAGE4_PARALLEL_STEPS", "false")
    order = []
    monkeypatch.setattr(fact_checker, "find_near_matches", lambda c: order.append("near") or c)
    monkeypatch.setattr(contradiction_detector, "detect", lambda c: order.append("detect") or ({}, []))
    run_once()
    assert order == ["near", "detect"]


def test_an_error_in_the_near_step_still_fails_the_sub_question_not_silently(monkeypatch):
    stub_everything_but_the_two_steps(monkeypatch)
    monkeypatch.setattr(fact_checker, "NEAR_ON", True)
    monkeypatch.setenv("STAGE4_PARALLEL_STEPS", "true")
    monkeypatch.setattr(fact_checker, "find_near_matches", lambda c: (_ for _ in ()).throw(RuntimeError("near broke")))
    monkeypatch.setattr(contradiction_detector, "detect", lambda c: ({}, []))
    with pytest.raises(RuntimeError, match="near broke"):
        run_once()                                   # run_factcheck turns this into {"error": ...} for the sub-question, as for any other error


def test_the_conflict_step_error_waits_for_the_near_thread_and_propagates(monkeypatch):
    stub_everything_but_the_two_steps(monkeypatch)
    monkeypatch.setattr(fact_checker, "NEAR_ON", True)
    monkeypatch.setenv("STAGE4_PARALLEL_STEPS", "true")
    finished = []
    monkeypatch.setattr(fact_checker, "find_near_matches", lambda c: finished.append("near") or c)
    monkeypatch.setattr(contradiction_detector, "detect", lambda c: (_ for _ in ()).throw(ConnectionError("db")))
    with pytest.raises(ConnectionError):
        run_once()
    assert finished == ["near"]


def test_the_near_evidence_holds_only_plain_fields_even_when_the_conflict_step_added_embeddings():
    import numpy as np
    member = {"source_id": "s", "source_title": "T", "quote": "q", "reliability": 0.8, "evidence_level": "full_text", "ev": 1.0, "weight": 0.8,
              "doc": "t", "q_emb": np.zeros(3), "claim": "other", "relation": "supports", "prob": 0.9}
    emb = lambda v: np.array(v, dtype=np.float32) / np.linalg.norm(v)      # noqa: E731
    a = {"claim": "one", "emb": emb([1, 0.2]), "members": [], "support": [{**member, "doc": "d1"}]}
    b = {"claim": "two", "emb": emb([1, 0.3]), "members": [], "support": [{**member, "doc": "d2"}]}
    import apps.api.agents.stage4_factcheck.fact_checker as fc
    orig = fc.judge_near_match
    fc.judge_near_match = lambda x, y, q: True
    try:
        fc.find_near_matches([a, b])
    finally:
        fc.judge_near_match = orig
    assert "q_emb" not in a["near"] and a["near"]["near_claim"] == "two" and a["near"]["relation"] == "near_match"


def test_preload_loads_the_model_once_in_the_background(monkeypatch):
    loaded = []
    monkeypatch.setattr(common, "_nli", None)
    monkeypatch.setattr(common, "CrossEncoder", lambda name: loaded.append(name) or object())
    common.preload_nli()
    for t in threading.enumerate():
        if t.name == "nli-preload":
            t.join(5)
    assert loaded == [common.NLI_MODEL]
    common.preload_nli()                              # already loaded: no second thread, no second load
    common._model()
    assert loaded == [common.NLI_MODEL]
    monkeypatch.setattr(common, "_nli", None)


def test_preload_swallows_a_load_error(monkeypatch):
    monkeypatch.setattr(common, "_nli", None)
    monkeypatch.setattr(common, "CrossEncoder", lambda name: (_ for _ in ()).throw(OSError("no disk")))
    common.preload_nli()
    for t in threading.enumerate():
        if t.name == "nli-preload":
            t.join(5)                                  # no exception escapes the thread; Stage 4 would raise its own error


def test_a_finished_sub_question_says_so_with_its_counts_and_its_worker(monkeypatch):
    stub_everything_but_the_two_steps(monkeypatch)
    monkeypatch.setattr(fact_checker, "NEAR_ON", False)
    monkeypatch.setattr(contradiction_detector, "detect", lambda c: ({}, [{"d": 1}, {"d": 2}]))
    monkeypatch.setattr(fact_checker, "label_clusters", lambda c, conflicts: [{"label": "supported", "contested": False, "evidence": []}, {"label": "unverified", "contested": False, "evidence": []}])
    reports = []
    out = {}

    def run():
        out["r"] = node._check_sub_question("q1", SimpleNamespace(id="s1", main_topic="topic"), lambda step, message, **data: reports.append((step, message, data)))
    t = threading.Thread(target=run, name="stage4-overlap_1")           # the second worker of the overlap pool
    t.start()
    t.join()
    steps = [r[0] for r in reports]
    assert steps[0] == "claims" and steps[-1] == "done"
    assert reports[0][2]["worker"] == 2
    done = reports[-1][2]
    assert done["worker"] == 2 and done["claims"] == 2 and done["supported"] == 1 and done["unverified"] == 1 and done["disagreements"] == 2
    assert {"judgeCalls", "judgeCacheHits", "judgeWaits", "judgeFailures"} <= set(done)
    run_in_main = node._check_sub_question("q1", SimpleNamespace(id="s1", main_topic="topic"), lambda step, message, **data: reports.append((step, message, data)))
    assert reports[-1][2]["worker"] is None                              # not a worker thread (the sequential path)
