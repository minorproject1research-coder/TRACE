"""Assigning the planner's flat query list to sub-questions: a query that does not fit its sub-question is dropped. Offline."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.api.agents.stage1_planner import question_generator as qg  # noqa: E402
from apps.api.models.task_plan import SubQuestion  # noqa: E402


class Embedder:
    """Unit vectors from a fixed table, so the similarities in each test are exactly the ones written down."""
    def __init__(self, table):
        self.table = table

    def encode(self, texts, normalize_embeddings=True):
        return np.array([self.table[t] for t in texts])


def unit(angle_degrees):
    a = np.radians(angle_degrees)
    return (float(np.cos(a)), float(np.sin(a)))


def sq(topic):
    return SubQuestion(main_topic=topic, detail_questions=[])


def run(monkeypatch, sub_topics, queries, vectors, min_sim=0.55):
    from apps.api.agents.stage2_retrieval import relevance_filter as rf
    table = {f"{t} ": vectors[t] for t in sub_topics}          # _assign_queries encodes "topic " + details (none here)
    table.update({q: vectors[q] for q in queries})
    monkeypatch.setattr(rf, "get_embedder", lambda: Embedder(table))
    monkeypatch.setattr(qg, "MIN_ASSIGN_SIMILARITY", min_sim)
    subs = [sq(t) for t in sub_topics]
    qg._assign_queries(subs, queries)
    return [s.queries for s in subs]


def test_a_query_forced_onto_a_poor_fit_is_dropped(monkeypatch):
    # A and B each fit two queries; "x" fits A best (cos 0.95) but A is full, so it is pushed to B at cos(80 deg) = 0.17
    vectors = {"A": unit(0), "B": unit(90), "a1": unit(5), "a2": unit(10), "x": unit(12), "b1": unit(85)}
    out = run(monkeypatch, ["A", "B"], ["a1", "a2", "x", "b1"], vectors)
    assert out[0] == ["a1", "a2"] and out[1] == ["b1"]          # x went to neither A (full) nor B (does not fit)


def test_with_the_gate_off_the_poor_fit_is_kept(monkeypatch):
    vectors = {"A": unit(0), "B": unit(90), "a1": unit(5), "a2": unit(10), "x": unit(12), "b1": unit(85)}
    out = run(monkeypatch, ["A", "B"], ["a1", "a2", "x", "b1"], vectors, min_sim=0.0)
    assert sorted(sum(out, [])) == ["a1", "a2", "b1", "x"]


def test_a_sub_question_can_end_with_no_query_so_expansion_takes_over(monkeypatch):
    vectors = {"A": unit(0), "B": unit(90), "a1": unit(2), "a2": unit(4), "a3": unit(6)}
    out = run(monkeypatch, ["A", "B"], ["a1", "a2", "a3"], vectors)
    assert out[1] == [] and set(out[0]) <= {"a1", "a2", "a3"}


def test_good_fits_are_untouched(monkeypatch):
    vectors = {"A": unit(0), "B": unit(40), "a1": unit(5), "b1": unit(35)}
    assert run(monkeypatch, ["A", "B"], ["a1", "b1"], vectors) == [["a1"], ["b1"]]
