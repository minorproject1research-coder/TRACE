"""Offline tests for the pure parts of tests/audit_tag_precision.py (sampling, blindness, consistency checks, latest run)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
import tests.audit_tag_precision as at  # noqa: E402


def make_pool():
    pool, n = [], 0
    for q in at.AUDIT_QUERY_IDS:
        for a in range(4):
            for j in range(9):
                n += 1
                final = ["yes", "yes", "partial", "no", "yes", "partial", None, "yes", "no"][j]
                strength = "full" if j % 2 == 0 else ("partial" if j % 3 == 0 else None)
                covered = a != 3
                kind, basis = at.classify(final, strength, covered)
                pool.append({"query_id": q, "sub_question_id": q[:4], "main_topic": "t", "source_id": f"s{j}", "digest_id": f"d{n}",
                             "finding_idx": j, "claim": f"claim {n}", "quote": f"quote {n}", "finding_key": f"f{n}", "kind": kind,
                             "covering_basis": basis, "aspect_idx": a, "aspect_text": f"{q[:4]}-aspect{a}", "strength": strength or "",
                             "final": final, "aspect_covered": covered, "similarity_val": 0.5 + (n % 10) / 20})
        for u in range(4):
            n += 1
            pool.append({"query_id": q, "sub_question_id": q[:4], "main_topic": "t", "source_id": "su", "digest_id": f"u{n}", "finding_idx": u,
                         "claim": f"untagged {n}", "quote": f"q {n}", "finding_key": f"u{n}", "kind": "untagged_candidate",
                         "covering_basis": "none", "aspect_idx": 0, "aspect_text": f"{q[:4]}-aspect0", "strength": "", "final": None,
                         "aspect_covered": True, "similarity_val": 0.6 + u / 50})
    return pool


def test_classify_judge_yes_needs_covered_aspect_and_ignores_tag_strength():
    assert at.classify("yes", None, True) == ("covering", "judge_yes")           # untagged but judged yes
    assert at.classify("yes", "partial", True) == ("covering", "judge_yes")
    assert at.classify("partial", "full", True) == ("tagged", "tag_full")        # full tag the judge did not accept
    assert at.classify("no", "partial", True) == ("tagged", "none")
    assert at.classify("yes", "full", False) == ("tagged", "tag_full")           # yes on an aspect that is NOT covered
    assert at.classify(None, None, True) == ("untagged", "none")


def test_sample_meets_quotas_and_is_deterministic():
    pool = make_pool()
    a = at.sample_pool(pool, 50, 11)
    b = at.sample_pool(pool, 50, 11)
    assert [c["finding_key"] for c in a] == [c["finding_key"] for c in b]
    csv_rows, side = at.build_outputs(a)
    counts = at.assert_consistent(csv_rows, side, n_min=45)
    assert counts["rows"] >= 45 and len(counts["per_query"]) == 3
    assert counts["per_kind"]["untagged"] >= 5 and counts["covered_aspect_partial_or_no"] >= 10
    assert all(s["final"] == "yes" for s in side.values() if s["covering_basis"] == "judge_yes")
    assert at.sample_pool(pool, 50, 12) != a


def test_csv_is_blind():
    csv_rows, side = at.build_outputs(at.sample_pool(make_pool(), 50, 11))
    assert set(csv_rows[0]) == set(at.CSV_FIELDS)
    assert {r["kind"] for r in csv_rows} <= {"tagged", "untagged"}


def test_consistency_check_catches_a_wrong_basis():
    csv_rows, side = at.build_outputs(at.sample_pool(make_pool(), 50, 11))
    rid = next(k for k, s in side.items() if s["covering_basis"] == "judge_yes")
    side[rid]["final"] = "partial"
    with pytest.raises(AssertionError):
        at.assert_consistent(csv_rows, side, n_min=45)


def test_latest_generation_drops_older_runs():
    rows = [{"sub_question_id": "a", "created_at": "2026-10-27T08:04:10+05:30", "i": 1},
            {"sub_question_id": "a", "created_at": "2026-10-29T10:20:00+05:30", "i": 2},
            {"sub_question_id": "a", "created_at": "2026-10-29T10:20:02+05:30", "i": 3},
            {"sub_question_id": "b", "created_at": "2026-10-24T09:58:00+05:30", "i": 4}]
    assert sorted(r["i"] for r in at.latest_generation(rows)) == [2, 3, 4]


def test_covered_by_index_not_by_text():
    cov = {"aspect_evidence": {
        "0": [{"verdict": "yes", "source_id": "a"}, {"verdict": "yes", "source_id": "b"}],      # covered
        "1": [],                                                                                # no evidence
        "2": [{"verdict": "yes", "source_id": "a"}, {"verdict": "yes", "source_id": "a"}],      # two yes, ONE source
        "3": [{"verdict": "yes", "source_id": "a"}]},                                           # one yes
        "uncovered_aspects": ["a reworded text that matches nothing today"]}
    assert at.covered_indices(cov, 5) == {0}
    assert at.covered_indices({}, 3) == set()                                                   # fallback rows carry no evidence


def test_stored_verdict_keeps_the_aspect_text():
    from apps.api.agents.stage3_summarizer.evidence_judge import write_verdicts_to_findings
    import hashlib
    digests = [{"source_id": "s1", "findings": [{"claim": "c1", "quote": "q", "verified": True}]}]
    cand = [{"aspect_idx": 0, "aspect_text": "how it works", "source_id": "s1", "claim": "c1", "digest_idx": 0, "finding_idx": 0}]
    key = (0, "s1", hashlib.sha256(b"c1").hexdigest()[:16])
    write_verdicts_to_findings(digests, cand, {key: {"verdict": {"final": "yes", "quote_supports_claim": "yes", "answers_aspect": "yes", "reason": "r"}}})
    assert digests[0]["findings"][0]["judge"]["0"]["aspect"] == "how it works"


def test_split_mismatch_is_an_error_not_a_silent_drop():
    digests = [{"findings": [{"judge": {"0": {}, "5": {}}}]}]
    at.check_split_matches_run("sq", ["a"] * 6, digests)                 # 6 aspects cover index 5: fine
    with pytest.raises(at.SplitMismatch):
        at.check_split_matches_run("sq", ["a"] * 5, digests)             # verdict for index 5 but only 5 aspects
    at.check_split_matches_run("sq", ["a"], [{"findings": [{}]}])        # no verdicts at all: nothing to check
