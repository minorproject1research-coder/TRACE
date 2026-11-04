"""Offline tests of the ONE_FINDING_ONE_ASPECT rule (coverage_check.assign_best_aspect and its use in check_coverage_judged)."""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.api.agents.stage3_summarizer import coverage_check as cc  # noqa: E402


def h(claim):
    return hashlib.sha256(claim.encode()).hexdigest()[:16]


def test_pure_function_keeps_the_most_similar_aspect_only():
    yes = {0: [(0, "s1", h("c1"))], 1: [(1, "s1", h("c1")), (1, "s2", h("c2"))], 2: [(2, "s1", h("c1"))]}
    sims = {(0, "s1", h("c1")): 0.50, (1, "s1", h("c1")): 0.71, (2, "s1", h("c1")): 0.60, (1, "s2", h("c2")): 0.40}
    kept, dropped = cc.assign_best_aspect(yes, sims)
    assert kept == {0: [], 1: [(1, "s1", h("c1")), (1, "s2", h("c2"))], 2: []}
    assert dropped == 2


def test_tie_goes_to_the_lower_aspect_index_and_other_findings_are_untouched():
    yes = {0: [(0, "s1", h("a"))], 3: [(3, "s1", h("a")), (3, "s2", h("b"))]}
    kept, dropped = cc.assign_best_aspect(yes, {})
    assert kept[0] == [(0, "s1", h("a"))] and kept[3] == [(3, "s2", h("b"))] and dropped == 1


def test_same_claim_from_two_sources_is_two_findings():
    yes = {0: [(0, "s1", h("c")), (0, "s2", h("c"))], 1: [(1, "s1", h("c")), (1, "s2", h("c"))]}
    sims = {(0, "s1", h("c")): 0.9, (1, "s1", h("c")): 0.5, (0, "s2", h("c")): 0.5, (1, "s2", h("c")): 0.9}
    kept, dropped = cc.assign_best_aspect(yes, sims)
    assert kept[0] == [(0, "s1", h("c"))] and kept[1] == [(1, "s2", h("c"))] and dropped == 2


def _scenario():
    verdict = {"verdict": {"final": "yes", "quote_supports_claim": "yes", "answers_aspect": "yes", "reason": ""}}
    digests = [{"source_id": s, "evidence_level": "full_text", "findings": [{"claim": c, "verified": True}]} for s, c in (("s1", "c1"), ("s2", "c2"))]
    verdicts = {(a, s, h(c)): verdict for a in (0, 1) for s, c in (("s1", "c1"), ("s2", "c2"))}
    sim = {(0, "s1"): 0.8, (1, "s1"): 0.4, (0, "s2"): 0.3, (1, "s2"): 0.7}
    candidates = [{"aspect_idx": a, "source_id": s, "claim": c, "quote": "q", "item_id": f"{a}{s}", "similarity": sim[(a, s)]}
                  for a in (0, 1) for s, c in (("s1", "c1"), ("s2", "c2"))]
    return digests, verdicts, candidates


def test_flag_off_both_aspects_covered_by_the_same_two_findings(monkeypatch):
    monkeypatch.delenv("ONE_FINDING_ONE_ASPECT", raising=False)
    digests, verdicts, candidates = _scenario()
    r = cc.check_coverage_judged(["a", "b"], [0, 1], ["a", "b"], digests, verdicts, candidates=candidates)
    assert r["uncovered_aspects"] == [] and set(r["judge_stats"]) == {"candidates", "yes", "partial", "no", "error"}


def test_flag_on_each_finding_covers_one_aspect(monkeypatch):
    monkeypatch.setenv("ONE_FINDING_ONE_ASPECT", "true")
    digests, verdicts, candidates = _scenario()
    r = cc.check_coverage_judged(["a", "b"], [0, 1], ["a", "b"], digests, verdicts, candidates=candidates)
    # c1 -> aspect a (0.8), c2 -> aspect b (0.7): each aspect keeps ONE yes, below JUDGE_MIN_YES = 2
    assert r["uncovered_aspects"] == ["a", "b"]
    assert r["uncovered_reasons"] == {"a": "judged_insufficient", "b": "judged_insufficient"}
    assert r["judge_stats"]["one_finding_one_aspect_dropped"] == 2
    assert [e["source_id"] for e in r["aspect_evidence"][0]] == ["s1"] and [e["source_id"] for e in r["aspect_evidence"][1]] == ["s2"]


def test_margin_keeps_near_ties_and_drops_clear_losers():
    yes = {0: [(0, "s1", h("c1"))], 1: [(1, "s1", h("c1"))], 2: [(2, "s1", h("c1"))]}
    sims = {(0, "s1", h("c1")): 0.70, (1, "s1", h("c1")): 0.72, (2, "s1", h("c1")): 0.55}
    kept, dropped = cc.assign_best_aspect(yes, sims, margin=0.05)
    assert kept == {0: [(0, "s1", h("c1"))], 1: [(1, "s1", h("c1"))], 2: []} and dropped == 1     # 0.70 is within 0.05 of 0.72; 0.55 is not
    kept0, dropped0 = cc.assign_best_aspect(yes, sims, margin=0.0)
    assert kept0 == {0: [], 1: [(1, "s1", h("c1"))], 2: []} and dropped0 == 2                       # default behaviour unchanged


def test_margin_env_parsing(monkeypatch):
    monkeypatch.delenv("ONE_FINDING_MARGIN", raising=False)
    assert cc.one_finding_margin() == 0.0
    monkeypatch.setenv("ONE_FINDING_MARGIN", "0.05")
    assert cc.one_finding_margin() == 0.05
    monkeypatch.setenv("ONE_FINDING_MARGIN", "abc")
    assert cc.one_finding_margin() == 0.0
