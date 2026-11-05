"""Loop 2 query step: new queries for one uncovered aspect. Offline: fake planner and a word-overlap embedder."""
import hashlib
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.api.agents.stage1_planner import gap_queries as gq  # noqa: E402
from apps.api.services.trace_llm_service import TraceLLMError  # noqa: E402


class WordEmbedder:
    """Cosine = word overlap: texts with the same words are identical, texts with no common word are orthogonal."""
    DIM = 1024

    def encode(self, texts, normalize_embeddings=True):
        out = np.zeros((len(texts), self.DIM))
        for row, text in enumerate(texts):
            for word in set(text.lower().split()):
                out[row, int(hashlib.md5(word.encode()).hexdigest(), 16) % self.DIM] = 1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        return out / np.where(norms == 0, 1, norms)


def plans(*query_lists):
    return [{"sub_questions": [{"topic": "t", "details": ["d"]}], "search_queries": list(q)} for q in query_lists]


def planner_returning(*query_lists):
    calls = []

    def planner(question, n, temperature):
        calls.append((question, n, temperature))
        return plans(*query_lists)
    planner.calls = calls
    return planner


ASPECT = "How is training memory cost measured for state space models?"
SUBQ = "How are SSMs and transformers trained and evaluated?"


def test_a_full_question_aspect_is_used_as_it_is():
    assert gq.standalone_question(ASPECT, SUBQ) == ASPECT


def test_a_vague_aspect_gets_its_sub_question_as_context():
    out = gq.standalone_question("parameters of a transformer", "What are transformers and how do they work?")
    assert out.startswith("Parameters of a transformer") and "What are transformers and how do they work?" in out
    short = gq.standalone_question("How does it work?", SUBQ)
    assert SUBQ in short                                    # a short question is as vague as a phrase


def test_the_planner_is_asked_for_several_plans_at_a_raised_temperature():
    planner = planner_returning(["alpha beta"])
    gq.generate(ASPECT, SUBQ, [], planner=planner, embedder=WordEmbedder())
    question, n, temperature = planner.calls[0]
    assert question == ASPECT and n == gq.GAP_PLANS and temperature == gq.GAP_TEMPERATURE


def test_the_anchor_is_added_to_the_planner_question():
    """Without it 'What are the parameters of a transformer?' came back with electrical-transformer queries (live check, 2026-11-05)."""
    planner = planner_returning(["alpha beta"])
    gq.generate(ASPECT, SUBQ, [], "deep learning", planner=planner, embedder=WordEmbedder())
    assert planner.calls[0][0] == f"{ASPECT} (deep learning)"


def test_queries_already_tried_or_repeated_across_plans_are_dropped():
    planner = planner_returning(
        ["training memory cost state space models measured", "gradient checkpointing mamba memory footprint tokens"],
        ["training memory cost state space models measured", "benchmark peak gpu memory mamba transformer training"],
        ["training memory cost state space models measured again"])
    tried = ["gradient checkpointing mamba memory footprint tokens"]
    out = gq.generate(ASPECT, SUBQ, tried, planner=planner, embedder=WordEmbedder())
    assert "gradient checkpointing mamba memory footprint tokens" not in out            # already tried
    assert sum("training memory cost state space models measured" in q for q in out) == 1   # repeated across plans and a near duplicate
    assert "benchmark peak gpu memory mamba transformer training" in out


def test_the_result_is_ranked_by_similarity_to_the_aspect_question_and_capped():
    planner = planner_returning(["overview of deep learning history", "training memory cost state space models measured",
                                 "mamba selective scan kernel", "peak memory state space models training how measured"],)
    out = gq.generate(ASPECT, SUBQ, [], planner=planner, embedder=WordEmbedder(), max_queries=2)
    assert len(out) == 2
    assert "overview of deep learning history" not in out                      # least related to the aspect
    assert out[0] == "training memory cost state space models measured"        # most related first


def test_the_domain_anchor_is_applied_once():
    planner = planner_returning(["state space models memory", "state space models memory deep learning"])
    out = gq.generate(ASPECT, SUBQ, [], anchor="deep learning", planner=planner, embedder=WordEmbedder())
    assert out and all(q.endswith("deep learning") and q.count("deep learning") == 1 for q in out)


def test_tried_queries_with_the_anchor_match_candidates_without_it():
    planner = planner_returning(["state space models memory cost"])
    tried = ["state space models memory cost deep learning"]            # stored with the anchor appended, as Stage 1 does
    assert gq.generate(ASPECT, SUBQ, tried, anchor="deep learning", planner=planner, embedder=WordEmbedder()) == []


def test_a_server_error_or_no_usable_plan_gives_no_queries_not_an_exception():
    def down(question, n, temperature):
        raise TraceLLMError("unreachable")
    assert gq.generate(ASPECT, SUBQ, [], planner=down, embedder=WordEmbedder()) == []
    assert gq.generate(ASPECT, SUBQ, [], planner=lambda q, n, t: [], embedder=WordEmbedder()) == []


def test_without_a_working_embedder_exact_duplicates_are_still_removed():
    class Broken:
        def encode(self, *a, **k):
            raise RuntimeError("no model")
    planner = planner_returning(["Alpha Beta", "gamma delta"], ["alpha beta", "epsilon"])
    out = gq.generate(ASPECT, SUBQ, ["gamma delta"], planner=planner, embedder=Broken())
    assert [q.lower() for q in out] == ["alpha beta", "epsilon"]


def test_plans_are_interleaved_so_one_plan_cannot_crowd_out_the_others():
    planner = planner_returning(["p1 one", "p1 two", "p1 three"], ["p2 one"], ["p3 one"])
    out = gq.generate(ASPECT, SUBQ, [], planner=planner, embedder=WordEmbedder(), max_queries=3)
    assert set(out) == {"p1 one", "p2 one", "p3 one"}
