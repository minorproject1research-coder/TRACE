"""Offline tests of the Stage 1 domain anchor (fake LLM, no network)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.api.agents.stage1_planner import domain_anchor as da  # noqa: E402
from apps.api.services import llm_service  # noqa: E402

QUESTION = "How do state space models like Mamba compare with transformers in training efficiency?"


@pytest.fixture
def fake_llm(monkeypatch):
    calls = []

    def fake(prompt, *, temperature=0.1, seed=None):
        calls.append(prompt)
        if isinstance(fake.reply, Exception):
            raise fake.reply
        return fake.reply
    fake.reply = {"anchor": "deep learning", "context": "Deep-learning sequence models such as Mamba; not electrical transformers."}
    monkeypatch.setattr(llm_service, "squeezer_json", fake)
    monkeypatch.setenv("DOMAIN_ANCHOR", "true")
    return fake, calls


# ---- pure helpers
def test_apply_to_queries_appends_the_anchor():
    out = da.apply_to_queries(["transformers overview", "Transformers Limits"], "deep learning")
    assert out == ["transformers overview deep learning", "Transformers Limits deep learning"]


def test_query_that_already_has_the_anchor_words_is_left_alone():
    assert da.apply_to_queries(["Deep learning transformers", "transformers in deep-learning models"], "deep learning") == \
        ["Deep learning transformers", "transformers in deep-learning models"]


def test_duplicates_after_anchoring_are_dropped():
    assert da.apply_to_queries(["mamba deep learning", "mamba"], "deep learning") == ["mamba deep learning"]


def test_empty_anchor_changes_nothing():
    q = ["a b", "c d"]
    out = da.apply_to_queries(q, "")
    assert out == q and out is not q


def test_text_helpers():
    assert da.similarity_text("What are SSMs?", "deep learning") == "What are SSMs? (deep learning)"
    assert da.similarity_text("What are SSMs?", "") == "What are SSMs?"
    assert da.judge_text("What are SSMs?", "Deep learning, not statistics.") == "What are SSMs? [Field: Deep learning, not statistics.]"
    assert da.judge_text("What are SSMs?", "") == "What are SSMs?"


# ---- generation
def test_switch_off_means_no_call_and_empty_result(monkeypatch):
    monkeypatch.setenv("DOMAIN_ANCHOR", "false")
    monkeypatch.setattr(llm_service, "squeezer_json", lambda *a, **k: pytest.fail("the LLM must not be called when the switch is off"))
    assert da.generate(QUESTION) == da.DomainAnchor() and not da.generate(QUESTION)


def test_switch_is_on_by_default_and_can_be_turned_off(monkeypatch):
    monkeypatch.delenv("DOMAIN_ANCHOR", raising=False)
    assert da.enabled() is True
    for off in ("false", "0", "no", "off", "False"):
        monkeypatch.setenv("DOMAIN_ANCHOR", off)
        assert da.enabled() is False


def test_prompt_formats_without_a_key_error():
    """The prompt holds a JSON example with doubled braces; a stray single brace would raise KeyError at runtime (as it did in the judge)."""
    text = da.PROMPT.format(question="Is this fine?")
    assert "Question: Is this fine?" in text and '{"ambiguous"' in text and "{question}" not in text


def test_generate_returns_and_caches(fake_llm):
    fake, calls = fake_llm
    a = da.generate(QUESTION)
    b = da.generate(QUESTION)
    assert a == b and a.anchor == "deep learning" and "not electrical" in a.context and len(calls) == 1


def test_different_question_is_a_different_cache_entry(fake_llm):
    fake, calls = fake_llm
    da.generate(QUESTION)
    da.generate(QUESTION + " in 2025")
    assert len(calls) == 2


def test_failed_call_gives_empty_and_is_not_cached(fake_llm):
    fake, calls = fake_llm
    fake.reply = RuntimeError("429")
    assert da.generate(QUESTION) == da.DomainAnchor()
    fake.reply = {"anchor": "deep learning", "context": "c"}
    assert da.generate(QUESTION).anchor == "deep learning" and len(calls) == 2


def test_unambiguous_question_gets_an_empty_anchor_and_no_context(fake_llm):
    fake, _ = fake_llm
    fake.reply = {"anchor": "", "context": "A sentence that must be dropped because there is no anchor."}
    a = da.generate(QUESTION)
    assert a.anchor == "" and a.context == "" and not a


@pytest.mark.parametrize("bad", [
    {"anchor": "one two three four five", "context": "x"},         # too many words
    {"anchor": "x" * 60, "context": "x"},                          # too long
    {"anchor": "deep [learning]", "context": "x"},                 # looks like markup
    {"anchor": 7, "context": "x"},                                 # not a string
    ["anchor"], "text", None,                                      # not an object
])
def test_unusable_model_output_becomes_empty(fake_llm, bad):
    fake, _ = fake_llm
    fake.reply = bad
    assert not da.generate(QUESTION)


def test_typographic_characters_become_plain_ascii(fake_llm):
    """A non-breaking hyphen in the context made the Windows log file (cp1252) drop the whole log line."""
    fake, _ = fake_llm
    fake.reply = {"anchor": "deep‑learning", "context": "control‑theory state‑space “models”—not ‘this’"}
    a = da.generate(QUESTION)
    assert a.anchor == "deep-learning"
    assert a.context == "control-theory state-space \"models\"-not 'this'"
    assert a.anchor.isascii() and a.context.isascii()


def test_overlong_context_is_dropped_but_the_anchor_is_kept(fake_llm):
    fake, _ = fake_llm
    fake.reply = {"anchor": "deep learning", "context": "x" * 400}
    a = da.generate(QUESTION)
    assert a.anchor == "deep learning" and a.context == ""


# ---- wiring
def _patch_filter(monkeypatch, seen):
    from apps.api.agents.stage2_retrieval import relevance_filter as rf

    def prefilter(text, ps, top_k, min_similarity):
        seen["sim"] = text
        return ps

    def judge(q, p):
        seen["judge"] = q
        return {"relevant": True, "confidence": 0.9, "reason": ""}
    monkeypatch.setattr(rf, "USE_LLM_JUDGMENT", True)
    monkeypatch.setattr(rf, "embedding_prefilter", prefilter)
    monkeypatch.setattr(rf, "llm_judge_relevance", judge)
    return rf


def test_filter_relevant_uses_the_anchor_for_similarity_and_the_context_for_the_judge(monkeypatch):
    seen = {}
    rf = _patch_filter(monkeypatch, seen)
    out = rf.filter_relevant("What are transformers?", [{"title": "A"}, {"title": "B"}], anchor="deep learning",
                             context="Neural networks, not power transformers.")
    assert seen["sim"] == "What are transformers? (deep learning)"
    assert seen["judge"] == "What are transformers? [Field: Neural networks, not power transformers.]" and len(out) == 2


def test_filter_relevant_without_anchor_is_unchanged(monkeypatch):
    seen = {}
    rf = _patch_filter(monkeypatch, seen)
    rf.filter_relevant("What are transformers?", [{"title": "A"}])
    assert seen == {"sim": "What are transformers?", "judge": "What are transformers?"}


def _plan_node(monkeypatch, anchor):
    from apps.api.graph import state as st
    from apps.api.graph.nodes import planner_node as pn
    from apps.api.models.task_plan import SubQuestion
    sqs = [SubQuestion(main_topic="What are transformers?", detail_questions=["d"], queries=["transformers overview", "transformers limits"])]
    monkeypatch.setattr(pn.question_generator, "generate", lambda q: sqs)
    monkeypatch.setattr(pn.db_service, "write_task_plan", lambda plan: None)
    monkeypatch.setattr(pn.domain_anchor, "generate", lambda q: anchor)
    return pn.planner_node(st.SharedResearchState(raw_query=QUESTION))["task_plan"]


def test_planner_node_anchors_the_queries_and_fills_the_plan(monkeypatch):
    plan = _plan_node(monkeypatch, da.DomainAnchor("deep learning", "Neural networks."))
    assert plan.domain_anchor == "deep learning" and plan.domain_context == "Neural networks."
    assert plan.sub_questions[0].queries == ["transformers overview deep learning", "transformers limits deep learning"]


def test_planner_node_without_anchor_leaves_queries_alone(monkeypatch):
    plan = _plan_node(monkeypatch, da.DomainAnchor())
    assert plan.sub_questions[0].queries == ["transformers overview", "transformers limits"]
    assert plan.domain_anchor == "" and plan.domain_context == ""


def test_task_plan_fields_do_not_reach_the_database_rows():
    from apps.api.models.task_plan import SubQuestion, TaskPlan
    plan = TaskPlan(raw_query="q", sub_questions=[SubQuestion(main_topic="t", detail_questions=["d"], queries=["x"])],
                    domain_anchor="deep learning", domain_context="c")
    sub_rows, query_rows = plan.to_supabase_rows()
    assert "deep learning" not in repr(sub_rows) and query_rows == [{"sub_question_id": plan.sub_questions[0].id, "query_text": "x"}]
