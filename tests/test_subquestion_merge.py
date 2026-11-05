"""Sub-question merge: different questions must stay apart. The pairs below are the merges the pipeline actually made (logs, Oct-Nov 2026)."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.api.agents.stage1_planner import question_generator as qg  # noqa: E402
from apps.api.models.task_plan import SubQuestion  # noqa: E402

WRONG_MERGES = [      # (kept question, question that was merged into it, logged similarity)
    ("How do LoRA and full fine-tuning compare in terms of performance?", "How do LoRA and full fine-tuning compare in terms of memory cost?", 0.95),
    ("What are the challenges or problems that transformer models face with long context windows?",
     "What are the techniques or methods that address the challenges or problems of transformer models with long context windows?", 0.95),
    ("How do state space models and transformers compare in training efficiency?", "How do state space models and transformers compare in long-sequence performance?", 0.93),
]
TRUE_DUPLICATE = ("How does speculative decoding affect LLM inference latency?", "How effective is speculative decoding at reducing LLM inference latency?", 0.97)


def sq(topic, details=None):
    return SubQuestion(main_topic=topic, detail_questions=details or [f"detail of {topic[:20]}"])


@pytest.mark.parametrize("a,b,sim", WRONG_MERGES)
def test_default_mode_keeps_different_questions_apart(a, b, sim, monkeypatch):
    monkeypatch.delenv("SUBQUESTION_MERGE", raising=False)
    out = qg._merge_similar([sq(a), sq(b)])
    assert [s.main_topic for s in out] == [a, b]


def test_default_mode_also_keeps_the_one_true_duplicate_apart(monkeypatch):
    """The documented price of the default: a paraphrased duplicate costs extra search time; it is not merged."""
    monkeypatch.delenv("SUBQUESTION_MERGE", raising=False)
    a, b, _ = TRUE_DUPLICATE
    assert len(qg._merge_similar([sq(a), sq(b)])) == 2


def test_identical_content_words_are_merged_and_details_are_absorbed(monkeypatch):
    monkeypatch.delenv("SUBQUESTION_MERGE", raising=False)
    absorbed = []
    monkeypatch.setattr(qg, "_absorb_details", lambda host, other, model: absorbed.append((host.main_topic, other.main_topic)))
    from apps.api.agents.stage2_retrieval import relevance_filter as rf
    monkeypatch.setattr(rf, "get_embedder", lambda: object())
    first, second, other = sq("What is LoRA fine-tuning?"), sq("What is the LoRA fine-tuning"), sq("What is full fine-tuning?")
    out = qg._merge_similar([first, second, other])
    assert out == [first, other] and absorbed == [("What is LoRA fine-tuning?", "What is the LoRA fine-tuning")]


def test_plural_and_case_and_punctuation_do_not_matter(monkeypatch):
    monkeypatch.delenv("SUBQUESTION_MERGE", raising=False)
    monkeypatch.setattr(qg, "_absorb_details", lambda *a: None)
    from apps.api.agents.stage2_retrieval import relevance_filter as rf
    monkeypatch.setattr(rf, "get_embedder", lambda: object())
    assert len(qg._merge_similar([sq("What are transformer models?"), sq("what are Transformer model")])) == 1


def test_off_mode_never_merges(monkeypatch):
    monkeypatch.setenv("SUBQUESTION_MERGE", "off")
    assert len(qg._merge_similar([sq("What is X?"), sq("What is X?")])) == 2


def test_unknown_mode_falls_back_to_exact(monkeypatch):
    monkeypatch.setenv("SUBQUESTION_MERGE", "nonsense")
    assert qg._merge_mode() == "exact"


def test_embedding_mode_uses_its_threshold(monkeypatch):
    monkeypatch.setenv("SUBQUESTION_MERGE", "embedding")
    monkeypatch.setattr(qg, "MERGE_SIMILARITY", 0.97)
    monkeypatch.setattr(qg, "_absorb_details", lambda *a: None)

    class Fake:
        def encode(self, texts, normalize_embeddings=True):
            # row i of the result is a unit vector; q0 and q1 have cosine 0.98, q2 is 0.95 from q0
            vecs = {"q0": (1.0, 0.0), "q1": (0.98, (1 - 0.98 ** 2) ** 0.5), "q2": (0.95, (1 - 0.95 ** 2) ** 0.5)}
            return np.array([vecs[t] for t in texts])
    from apps.api.agents.stage2_retrieval import relevance_filter as rf
    monkeypatch.setattr(rf, "get_embedder", lambda: Fake())
    out = qg._merge_similar([sq("q0"), sq("q1"), sq("q2")])
    assert [s.main_topic for s in out] == ["q0", "q2"]      # q1 (0.98) merged, q2 (0.95) kept


def test_build_sub_questions_keeps_both_dimensions_of_the_mamba_question(monkeypatch):
    monkeypatch.delenv("SUBQUESTION_MERGE", raising=False)
    plan = {"sub_questions": [
        {"topic": "How do state space models and transformers compare in training efficiency?", "details": ["d1"]},
        {"topic": "How do state space models and transformers compare in long-sequence performance?", "details": ["d2"]}]}
    topics = [s.main_topic for s in qg._build_sub_questions(plan)]
    assert len(topics) == 2 and "long-sequence performance" in topics[1]
