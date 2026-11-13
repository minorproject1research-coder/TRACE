"""Opt-in plan cache (PLAN_CACHE=true) and the planner client's alternative plans (decompose_many). All offline."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.api.agents.stage1_planner import plan_cache, question_generator as qg  # noqa: E402
from apps.api.services import trace_llm_service as t  # noqa: E402
from apps.api.services.trace_llm_service import TraceLLMError  # noqa: E402

Q = "How do state space models like Mamba compare with transformers?"
PLAN = {"sub_questions": [{"topic": "What are state space models?", "details": ["How do they work?"]},
                          {"topic": "How do they compare with transformers?", "details": ["training cost"]}],
        "search_queries": ["state space models overview", "mamba vs transformer efficiency"]}


def test_when_off_nothing_is_stored_or_loaded(tmp_path, monkeypatch):
    monkeypatch.setenv("PLAN_CACHE", "false")
    plan_cache.store(Q, PLAN)
    assert plan_cache.load(Q) is None
    assert not (tmp_path / "plan_cache").exists()


def test_stored_plan_is_loaded_back_when_on(monkeypatch):
    monkeypatch.setenv("PLAN_CACHE", "true")
    assert plan_cache.load(Q) is None
    plan_cache.store(Q, PLAN)
    assert plan_cache.load(Q) == PLAN
    assert plan_cache.load("A different question?") is None


def test_whitespace_in_the_question_does_not_matter_but_the_tag_does(monkeypatch):
    monkeypatch.setenv("PLAN_CACHE", "true")
    plan_cache.store(Q, PLAN)
    assert plan_cache.load("  How do state space models like Mamba   compare with transformers?\n") == PLAN
    monkeypatch.setenv("PLAN_CACHE_TAG", "planner-v2")
    assert plan_cache.load(Q) is None


def test_switch_values(monkeypatch):
    for value, expected in (("true", True), ("1", True), ("on", True), ("false", False), ("", False), ("nonsense", False)):
        monkeypatch.setenv("PLAN_CACHE", value)
        assert plan_cache.enabled() is expected


def test_unreadable_or_unusable_cache_file_means_plan_again(monkeypatch):
    monkeypatch.setenv("PLAN_CACHE", "true")
    plan_cache.store(Q, PLAN)
    path = plan_cache.cache_path(Q)
    path.write_text("{not json", encoding="utf-8")
    assert plan_cache.load(Q) is None
    path.write_text(json.dumps({"question": Q, "plan": {"sub_questions": [], "search_queries": []}}), encoding="utf-8")
    assert plan_cache.load(Q) is None
    plan_cache.store(Q, {"sub_questions": [], "search_queries": []})        # an unusable plan is never written
    assert plan_cache.load(Q) is None


def _count_calls(monkeypatch, plan=PLAN):
    calls = []
    monkeypatch.setattr(t, "decompose", lambda q, *a, **k: calls.append(q) or json.loads(json.dumps(plan)))
    return calls


def test_generate_reuses_the_plan_when_on(monkeypatch):
    monkeypatch.setenv("PLAN_CACHE", "true")
    calls = _count_calls(monkeypatch)
    first = qg.generate(Q)
    second = qg.generate(Q)
    assert len(calls) == 1
    assert [s.main_topic for s in first] == [s.main_topic for s in second]
    assert [s.queries for s in first] == [s.queries for s in second]


def test_generate_plans_every_time_when_off(monkeypatch):
    monkeypatch.setenv("PLAN_CACHE", "false")
    calls = _count_calls(monkeypatch)
    qg.generate(Q)
    qg.generate(Q)
    assert len(calls) == 2


def test_a_groq_fallback_plan_is_not_cached(monkeypatch):
    monkeypatch.setenv("PLAN_CACHE", "true")
    monkeypatch.setattr(qg, "LLM_FALLBACK", "groq")
    monkeypatch.setattr(t, "decompose", lambda *a, **k: (_ for _ in ()).throw(TraceLLMError("down")))
    monkeypatch.setattr(qg, "_groq_decompose", lambda q: json.loads(json.dumps(PLAN)))
    qg.generate(Q)
    assert plan_cache.load(Q) is None


# ---------------------------------------------------------------- decompose_many

def _reply(queries):
    return json.dumps({"sub_questions": [{"topic": "What is X?", "details": ["d"]}], "search_queries": queries})


def test_decompose_many_returns_every_valid_plan(monkeypatch):
    sent = {}
    monkeypatch.setattr(t, "_request", lambda m, p, payload=None, retries=3: sent.update(payload) or
                        {"raw_output": _reply(["a"]), "raw_outputs": [_reply(["a"]), _reply(["b"]), _reply(["c"])]})
    plans = t.decompose_many("question", n=3, temperature=0.8)
    assert [p["search_queries"] for p in plans] == [["a"], ["b"], ["c"]]
    assert sent["n"] == 3 and sent["temperature"] == 0.8 and sent["question"] == "question"


def test_decompose_many_skips_bad_replies(monkeypatch):
    monkeypatch.setattr(t, "_request", lambda *a, **k: {"raw_output": "x", "raw_outputs": ["no json here", _reply(["b"]), '{"sub_questions": 5}']})
    plans = t.decompose_many("question")
    assert [p["search_queries"] for p in plans] == [["b"]]


def test_decompose_many_all_bad_returns_empty_not_an_error(monkeypatch):
    monkeypatch.setattr(t, "_request", lambda *a, **k: {"raw_output": "garbage", "raw_outputs": ["garbage"]})
    assert t.decompose_many("question") == []


def test_decompose_many_with_an_old_server_uses_the_single_reply(monkeypatch):
    monkeypatch.setattr(t, "_request", lambda *a, **k: {"raw_output": _reply(["only"])})
    assert [p["search_queries"] for p in t.decompose_many("question")] == [["only"]]


def test_decompose_many_caps_n_and_passes_server_errors_on(monkeypatch):
    sent = {}
    monkeypatch.setattr(t, "_request", lambda m, p, payload=None, retries=3: sent.update(payload) or {"raw_output": _reply(["a"])})
    t.decompose_many("question", n=99)
    assert sent["n"] == 4
    monkeypatch.setattr(t, "_request", lambda *a, **k: (_ for _ in ()).throw(TraceLLMError("unreachable")))
    with pytest.raises(TraceLLMError):
        t.decompose_many("question")


def test_plain_decompose_sends_only_the_old_fields(monkeypatch):
    sent = {}
    monkeypatch.setattr(t, "_request", lambda m, p, payload=None, retries=3: sent.update(payload) or {"raw_output": _reply(["a"])})
    t.decompose("question")
    assert set(sent) == {"question", "max_new_tokens"}
