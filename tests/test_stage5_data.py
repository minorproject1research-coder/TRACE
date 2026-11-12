"""Stage 5 data layer: loader, tiers, references. Offline: hand-made dicts and a fake database, no network, no model."""
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.api.agents.stage5_report import loader, references, tiers                       # noqa: E402
from apps.api.agents.stage5_report.references import ReferenceBook, domain_of, format_reference, render_marker   # noqa: E402
from apps.api.agents.stage5_report.schema import (Claim, Evidence, Reference, TIER_DISPUTED, TIER_PARTLY, TIER_SINGLE, TIER_SUPPORTED,   # noqa: E402
                                                  make_claim_id)
from apps.api.services import report_service                                                # noqa: E402


@pytest.fixture(autouse=True)
def _stage5_env(monkeypatch):
    for name in ("STAGE5_MAX_PER_SOURCE", "STAGE5_SINGLE_NEEDS_STRONG", "STAGE5_SCOPE_CHECK", "STAGE5_MAX_SINGLE_PER_SECTION", "STAGE5_ENTAIL_MIN"):
        monkeypatch.delenv(name, raising=False)


# ------------------------------------------------------------------------------------------------------------------------- builders
def ev(sid="s1", title="Paper One", quote="a verbatim quote", relation="supports", level="full_text", via=None, near_claim=None, prob=0.9):
    d = {"source_id": sid, "source_title": title, "quote": quote, "relation": relation, "reliability": 0.8, "evidence_level": level, "prob": prob, "via": via}
    if near_claim:
        d["near_claim"] = near_claim
    return d


def row(claim="Claim text", label="unverified", evidence=None, confidence=0.5, contested=False, support=None, contra=0):
    evidence = [ev()] if evidence is None else evidence
    return {"claim": claim, "label": label, "confidence": confidence, "contested": contested, "evidence": evidence,
            "support_doc_count": support if support is not None else len({e["source_title"] for e in evidence if e["relation"] == "supports"}),
            "contra_doc_count": contra}


def sq(sid="sq1", rows=(), contradictions=(), title="Topic?"):
    return {"id": sid, "title": title, "detail_questions": [], "claims": list(rows), "contradictions": list(contradictions)}


def build(rows, sid="sq1", **kw):
    return tiers.build_claims([sq(sid, rows)], **kw)


def by_text(claims):
    return {c.text: c for c in claims}


# ======================================================================================================== tier assignment
def test_supported_partly_single_tiers_keep_the_label():
    rows = [
        row("S", "supported", [ev("a", "Alpha"), ev("b", "Beta")], 0.9),
        row("P", "partially_supported", [ev("a", "Alpha"), ev("b", "Beta", relation="near_match", near_claim="B says close")], 0.6),
        row("U", "unverified", [ev("a", "Alpha")], 0.4),
    ]
    got = by_text(build(rows))
    assert (got["S"].tier, got["S"].label) == (TIER_SUPPORTED, "supported")
    assert (got["P"].tier, got["P"].label) == (TIER_PARTLY, "partially_supported")
    assert (got["U"].tier, got["U"].label) == (TIER_SINGLE, "unverified")
    assert all(c.filtered_reason is None for c in got.values())


def test_contradicted_and_contested_are_disputed_for_every_label():
    rows = [row("C", "contradicted", [ev("a", "Alpha"), ev("b", "Beta", relation="contradicts")], contra=1)]
    for label, ev_list in (("supported", [ev("a", "Alpha"), ev("c", "Gamma")]), ("partially_supported", [ev("a", "Alpha")]), ("unverified", [ev("a", "Alpha")])):
        rows.append(row("K-" + label, label, ev_list + [ev("b", "Beta", relation="contradicts")], contested=True, contra=1))
    got = by_text(build(rows))
    assert all(c.tier == TIER_DISPUTED for c in got.values())
    assert got["C"].label == "contradicted" and got["K-supported"].label == "supported" and got["K-supported"].contested


def test_unknown_label_and_incomplete_evidence_are_filtered_with_reason():
    rows = [
        row("weird", "maybe"),
        row("one doc under supported", "supported", [ev("a", "Alpha")]),
        row("same doc twice under supported", "supported", [ev("a", "Alpha"), ev("a2", "Alpha | Site")]),
        row("partly without near match", "partially_supported", [ev("a", "Alpha")]),
        row("no supporting quote", "unverified", [ev("a", "Alpha", relation="contradicts")]),
        row("empty quote", "unverified", [ev("a", "Alpha", quote="  ")]),
    ]
    got = by_text(build(rows))
    assert got["weird"].filtered_reason == tiers.FILTER_UNKNOWN
    for name in [r["claim"] for r in rows[1:]]:
        assert got[name].tier is None and got[name].filtered_reason == tiers.FILTER_INCOMPLETE, name


def test_row_without_claim_text_is_skipped_and_duplicate_wording_keeps_the_better_row():
    rows = [row("", "unverified"), row("Dup claim", "unverified", confidence=0.3), row("dup  CLAIM", "unverified", [ev("b", "Beta")], confidence=0.7)]
    claims = build(rows)
    assert len(claims) == 1 and claims[0].confidence == 0.7


def test_evidence_conversion_and_ref_key():
    c = build([row("X", "supported", [ev("a", "Vision Transformers | arXiv", via="stage3_judge"), ev("b", "Vision transformers - Blog", level="abstract")], 0.8)])[0]
    assert [e.ref_key for e in c.evidence] == ["vision transformers", "vision transformers"]  # same document under two source ids and sites
    assert c.evidence[0].via == "stage3_judge" and c.support_docs == 2 and c.confidence == 0.8
    # a claim whose two supports are the same document is not "two sources" -> filtered (see incomplete test)
    assert tiers.build_claims([sq("sq1", [row("Y", "supported", [ev("a", "T | A"), ev("b", "T - B")])])])[0].tier is None


def test_evidence_order_is_supports_then_near_then_contradicts():
    c = build([row("Z", "partially_supported", [ev("c", "Gamma", relation="contradicts"), ev("b", "Beta", relation="near_match", near_claim="n"), ev("a", "Alpha")])])[0]
    assert [e.relation for e in c.evidence] == ["supports", "near_match", "contradicts"]
    assert c.evidence[1].near_claim == "n" and len(c.supporting()) == 1 and len(c.conflicting()) == 1


def test_evidence_rows_as_json_string_and_missing_fields_are_tolerated():
    r = row("J", "unverified")
    r["evidence"] = '[{"source_id": "q", "source_title": null, "quote": "text here", "evidence_level": "full_text"}]'
    c = build([r])[0]
    assert c.tier == TIER_SINGLE and c.evidence[0].title == "" and c.evidence[0].relation == "supports" and c.evidence[0].ref_key == "q"


# ===================================================================================================== deterministic claim ids
def test_claim_ids_are_stable_across_reruns_and_row_order():
    rows = [row("First claim", "unverified", confidence=0.4), row("Second claim", "supported", [ev("a", "Alpha"), ev("b", "Beta")], 0.9)]
    first = build(rows)
    again = build(list(reversed([dict(r) for r in rows])))
    assert [c.claim_id for c in first] == [c.claim_id for c in again]       # same output order too
    assert by_text(first)["First claim"].claim_id == make_claim_id("sq1", "First claim")
    assert make_claim_id("sq1", "First  CLAIM ") == by_text(first)["First claim"].claim_id
    assert build(rows, sid="sq2")[0].claim_id != first[0].claim_id


def test_output_is_ordered_by_section_then_tier_then_confidence():
    inputs = [sq("a", [row("single hi", "unverified", confidence=0.5), row("sup", "supported", [ev("x", "X"), ev("y", "Y")], 0.9),
                       row("single lo", "unverified", [ev("z", "Z")], 0.2)]), sq("b", [row("other", "unverified", [ev("w", "W")])])]
    out = tiers.build_claims(inputs)
    assert [c.text for c in out] == ["sup", "single hi", "single lo", "other"]


# ============================================================================================================ single filters
def test_single_needs_strong_evidence_full_text_or_stage3_judge():
    rows = [row("weak abstract", "unverified", [ev("a", "A", level="abstract")]), row("weak snippet", "unverified", [ev("b", "B", level="web_snippet")]),
            row("full text", "unverified", [ev("c", "C", level="full_text")]), row("judged abstract", "unverified", [ev("d", "D", level="abstract", via="stage3_judge")])]
    got = by_text(build(rows))
    assert got["weak abstract"].filtered_reason == tiers.FILTER_WEAK and got["weak snippet"].tier is None
    assert got["full text"].tier == TIER_SINGLE and got["judged abstract"].tier == TIER_SINGLE
    assert by_text(build(rows, needs_strong=False))["weak abstract"].tier == TIER_SINGLE
    # the strong rule does not touch the other tiers
    assert build([row("S", "supported", [ev("a", "A", level="abstract"), ev("b", "B", level="abstract")])])[0].tier == TIER_SUPPORTED


def test_strong_rule_env_switch_is_read_at_call_time(monkeypatch):
    rows = [row("weak", "unverified", [ev("a", "A", level="abstract")])]
    assert build(rows)[0].tier is None
    monkeypatch.setenv("STAGE5_SINGLE_NEEDS_STRONG", "false")
    assert build(rows)[0].tier == TIER_SINGLE


def test_per_source_cap_keeps_the_best_three_per_document():
    rows = [row(f"claim {i}", "unverified", [ev("a", "Same Paper", quote=f"quote {i}")], confidence=0.1 * i) for i in range(1, 6)]
    claims = build(rows)
    kept = sorted(c.text for c in claims if c.tier == TIER_SINGLE)
    assert kept == ["claim 3", "claim 4", "claim 5"]
    assert all(c.filtered_reason == tiers.FILTER_SOURCE_CAP for c in claims if c.tier is None)


def test_per_source_cap_counts_the_same_document_under_two_source_ids_and_across_sections():
    s1 = sq("a", [row(f"a{i}", "unverified", [ev("id1", "Paper | Site")], confidence=0.9 - i * 0.1) for i in range(2)])
    s2 = sq("b", [row(f"b{i}", "unverified", [ev("id2", "paper")], confidence=0.5 - i * 0.1) for i in range(2)])
    claims = tiers.build_claims([s1, s2], per_source=3)
    assert sum(1 for c in claims if c.tier == TIER_SINGLE) == 3
    assert [c.text for c in claims if c.tier is None] == ["b1"]


def test_per_source_cap_env_and_zero_disables(monkeypatch):
    rows = [row(f"c{i}", "unverified", [ev("a", "P")], confidence=0.1 * i) for i in range(1, 5)]
    monkeypatch.setenv("STAGE5_MAX_PER_SOURCE", "1")
    assert sum(c.tier == TIER_SINGLE for c in build(rows)) == 1
    monkeypatch.setenv("STAGE5_MAX_PER_SOURCE", "0")
    assert sum(c.tier == TIER_SINGLE for c in build(rows)) == 4
    monkeypatch.setenv("STAGE5_MAX_PER_SOURCE", "garbage")                      # an unreadable value falls back to the default
    assert sum(c.tier == TIER_SINGLE for c in build(rows)) == 3


def test_section_cap_prefers_different_documents_then_confidence():
    rows = [row("A1", "unverified", [ev("a", "Doc A")], confidence=0.9), row("A2", "unverified", [ev("a", "Doc A")], confidence=0.8),
            row("B1", "unverified", [ev("b", "Doc B")], confidence=0.3), row("C1", "unverified", [ev("c", "Doc C")], confidence=0.2),
            row("D1", "unverified", [ev("d", "Doc D")], confidence=0.1)]
    claims = by_text(build(rows, per_section=3))
    assert {t for t, c in claims.items() if c.tier == TIER_SINGLE} == {"A1", "B1", "C1"}      # A2 (second of Doc A) loses to the other documents
    assert claims["A2"].filtered_reason == tiers.FILTER_SECTION_CAP and claims["D1"].filtered_reason == tiers.FILTER_SECTION_CAP
    assert {t for t, c in by_text(build(rows, per_section=4)).items() if c.tier == TIER_SINGLE} == {"A1", "B1", "C1", "D1"}


def test_section_cap_is_per_section_default_eight_and_full_text_ranks_first(monkeypatch):
    rows = [row(f"n{i}", "unverified", [ev(f"id{i}", f"Doc {i}")], confidence=0.5) for i in range(10)]
    assert sum(c.tier == TIER_SINGLE for c in build(rows)) == 8
    assert sum(c.tier == TIER_SINGLE for c in tiers.build_claims([sq("a", rows[:6]), sq("b", rows[6:] + [row("m", "unverified", [ev("z", "Z")])])])) == 11
    mixed = [row("judge", "unverified", [ev("a", "A", level="abstract", via="stage3_judge")], confidence=0.9),
             row("full", "unverified", [ev("b", "B", level="full_text")], confidence=0.1)]
    out = build(mixed, per_section=1)
    assert [c.text for c in out if c.tier == TIER_SINGLE] == ["full"]                  # full text beats a confirmed abstract, whatever the confidence
    monkeypatch.setenv("STAGE5_MAX_SINGLE_PER_SECTION", "2")
    assert sum(c.tier == TIER_SINGLE for c in build(rows)) == 2


def test_caps_do_not_touch_supported_partly_or_disputed():
    rows = [row(f"s{i}", "supported", [ev(f"a{i}", "Same"), ev(f"b{i}", f"Other {i}")]) for i in range(5)]
    assert sum(c.tier == TIER_SUPPORTED for c in build(rows, per_source=1, per_section=1)) == 5


def test_scope_check_is_off_by_default_and_injectable():
    calls = []
    rows = [row("broad", "unverified", [ev("a", "A", quote="narrow quote")]), row("fine", "unverified", [ev("b", "B", quote="fine quote")])]

    def check(claim, quote):
        calls.append((claim, quote))
        return claim != "broad"
    assert all(c.tier == TIER_SINGLE for c in build(rows, scope_check=check))      # switch off -> never called
    assert calls == []
    got = by_text(build(rows, scope_on=True, scope_check=check))
    assert got["broad"].filtered_reason == tiers.FILTER_SCOPE and got["fine"].tier == TIER_SINGLE
    assert ("broad", "narrow quote") in calls                                      # premise = the quote, hypothesis = the claim


def test_scope_check_fails_closed_and_env_switch(monkeypatch):
    rows = [row("x", "unverified")]

    def boom(claim, quote):
        raise RuntimeError("nli down")
    assert build(rows, scope_on=True, scope_check=boom)[0].filtered_reason == tiers.FILTER_SCOPE
    monkeypatch.setenv("STAGE5_SCOPE_CHECK", "true")
    assert tiers.scope_check_enabled() is True
    assert build(rows, scope_check=lambda c, q: True)[0].tier == TIER_SINGLE


def test_default_scope_check_fails_closed_without_model(monkeypatch):
    import apps.api.agents.stage4_factcheck.common as common
    monkeypatch.setattr(common, "nli_probs", lambda pairs: (_ for _ in ()).throw(RuntimeError("no model")))
    assert tiers.default_scope_check("claim", "quote") is False
    monkeypatch.setattr(common, "nli_probs", lambda pairs: [{"entailment": 0.8, "contradiction": 0.1, "neutral": 0.1}])
    assert tiers.default_scope_check("claim", "quote") is True


def test_count_claims():
    rows = [row("S", "supported", [ev("a", "A"), ev("b", "B")]), row("U", "unverified"), row("W", "unverified", [ev("c", "C", level="abstract")]),
            row("D", "contradicted", [ev("a", "A"), ev("z", "Z", relation="contradicts")], contra=1)]
    n = tiers.count_claims(build(rows))
    assert (n["total"], n["supported"], n["single"], n["disputed"], n["partly"]) == (4, 1, 1, 1, 0)
    assert n["filtered"] == {tiers.FILTER_WEAK: 1} and n["filtered_total"] == 1


# ================================================================================================================ jobs
def test_make_jobs_groups_same_tier_max_three_in_tier_then_confidence_order():
    rows = [row(f"u{i}", "unverified", [ev(f"id{i}", f"U{i}")], confidence=0.1 + i * 0.01) for i in range(7)]
    rows += [row("s1", "supported", [ev("a", "A"), ev("b", "B")], 0.9), row("p1", "partially_supported", [ev("a", "A"), ev("c", "C", relation="near_match")], 0.6),
             row("d1", "contradicted", [ev("a", "A"), ev("z", "Z", relation="contradicts")])]
    claims = build(rows, per_section=20)
    jobs = tiers.make_jobs("sec1", claims)
    assert [j.tier for j in jobs] == [TIER_SUPPORTED, TIER_PARTLY, TIER_SINGLE, TIER_SINGLE, TIER_SINGLE]
    assert [len(j.claims) for j in jobs] == [1, 1, 3, 3, 1]
    assert [c.text for c in jobs[2].claims] == ["u6", "u5", "u4"]                      # best confidence first
    assert all(len(j.claims) <= 3 and len({c.tier for c in j.claims}) == 1 and j.section_id == "sec1" for j in jobs)
    assert not any(c.text == "d1" for j in jobs for c in j.claims)                     # disputed claims are never written about


def test_make_jobs_skips_filtered_claims_and_clamps_group_size():
    rows = [row(f"u{i}", "unverified", [ev(f"id{i}", f"U{i}")]) for i in range(4)] + [row("weak", "unverified", [ev("w", "W", level="abstract")])]
    claims = build(rows)
    assert sum(len(j.claims) for j in tiers.make_jobs("s", claims)) == 4
    assert [len(j.claims) for j in tiers.make_jobs("s", claims, max_per_job=2)] == [2, 2]
    assert [len(j.claims) for j in tiers.make_jobs("s", claims, max_per_job=10)] == [3, 1]       # never more than 3
    assert tiers.make_jobs("s", []) == []


def test_partly_claims_get_one_job_each_other_tiers_up_to_three():
    rows = [row(f"p{i}", "partially_supported", [ev(f"a{i}", f"A{i}"), ev(f"c{i}", f"C{i}", relation="near_match")], 0.6 - i * 0.01) for i in range(4)]
    rows += [row(f"u{i}", "unverified", [ev(f"id{i}", f"U{i}")]) for i in range(4)]
    jobs = tiers.make_jobs("sec", build(rows, per_section=20))
    assert [len(j.claims) for j in jobs if j.tier == TIER_PARTLY] == [1, 1, 1, 1]      # claim + related wording of 3 claims never fit in 60 words
    assert [len(j.claims) for j in jobs if j.tier == TIER_SINGLE] == [3, 1]


def test_job_ids_are_deterministic_and_change_with_content():
    rows = [row(f"u{i}", "unverified", [ev(f"id{i}", f"U{i}")], confidence=0.1 * i) for i in range(1, 5)]
    a = tiers.make_jobs("sec", build(rows))
    b = tiers.make_jobs("sec", build(list(reversed(rows))))
    assert [j.job_id for j in a] == [j.job_id for j in b] and len({j.job_id for j in a}) == len(a)
    assert tiers.make_jobs("other", build(rows))[0].job_id != a[0].job_id
    assert a[0].job_id.startswith("j_")


# ========================================================================================================= disagreements
def disputed_claim(text="Model X beats Y", sid="sq1"):
    return build([row(text, "contradicted", [ev("a", "Paper A", quote="X beats Y on task"), ev("b", "Paper B | Site", quote="Y beats X", relation="contradicts")],
                      contra=1)], sid=sid)


def test_contradiction_row_links_to_claim_by_text_and_gets_ref_keys():
    claims = disputed_claim()
    rows = [{"claim_a": "model  X beats Y", "claim_b": "Y is better than X", "source_a_title": "Paper A", "source_b_title": "Paper B | Site",
             "quote_a": "X beats Y on task", "quote_b": "y beats x", "prob": 0.8, "reason": "opposite", "sub_question_id": "sq1"}]
    out = tiers.disputed_for_section(claims, rows)
    assert len(out) == 1
    d = out[0]
    assert d.claim_id == claims[0].claim_id and d.sub_question_id == "sq1"
    assert (d.ref_key_a, d.ref_key_b) == ("paper a", "paper b") and d.prob == 0.8 and d.reason == "opposite"
    assert d.quote_a == "X beats Y on task" and d.claim_b == "Y is better than X"


def test_contradiction_side_b_matched_by_title_when_quote_differs():
    out = tiers.disputed_for_section(disputed_claim(), [{"claim_a": "Model X beats Y", "claim_b": "b", "source_a_title": "", "source_b_title": "Paper B",
                                                         "quote_a": "", "quote_b": "something else", "sub_question_id": "sq1"}])
    assert out[0].ref_key_b == "paper b" and out[0].source_a_title == "Paper A" and out[0].quote_a == "X beats Y on task"   # filled from the claim's evidence


def test_unlinked_contradiction_row_is_kept_without_claim_id():
    out = tiers.disputed_for_section([], [{"claim_a": "Alpha", "claim_b": "Beta", "source_a_title": "T1 | s", "source_b_title": "T2", "quote_a": "qa", "quote_b": "qb",
                                           "sub_question_id": "sqX"}])
    assert len(out) == 1 and out[0].claim_id is None and out[0].sub_question_id == "sqX" and (out[0].ref_key_a, out[0].ref_key_b) == ("t1", "t2")


def test_disputed_claim_without_a_row_is_shown_from_its_own_evidence():
    out = tiers.disputed_for_section(disputed_claim(), [])
    assert len(out) == 1
    d = out[0]
    assert (d.claim_a, d.quote_a, d.quote_b, d.ref_key_a, d.ref_key_b) == ("Model X beats Y", "X beats Y on task", "Y beats X", "paper a", "paper b")
    assert d.claim_b == "Y beats X" and d.claim_id


def test_no_double_listing_when_row_and_claim_describe_the_same_conflict():
    claims = disputed_claim()
    rows = [{"claim_a": "Model X beats Y", "claim_b": "Y beats X", "source_a_title": "Paper A", "source_b_title": "Paper B", "quote_a": "X beats Y on task",
             "quote_b": "Y beats X", "sub_question_id": "sq1"}]
    assert len(tiers.disputed_for_section(claims, rows)) == 1


def test_contested_supported_claim_appears_but_normal_claims_do_not():
    claims = build([row("Contested one", "supported", [ev("a", "A"), ev("b", "B"), ev("c", "C", relation="contradicts", quote="not so")], contested=True, contra=1),
                    row("Plain", "supported", [ev("a", "A"), ev("b", "B")])])
    out = tiers.disputed_for_section(claims, [])
    assert [d.claim_a for d in out] == ["Contested one"] and out[0].quote_b == "not so"


def test_disputed_claim_without_conflicting_or_supporting_evidence_is_skipped_and_order_is_stable():
    broken = build([row("No conflict", "contradicted", [ev("a", "A")]), row("No support", "contradicted", [ev("z", "Z", relation="contradicts")])])
    assert tiers.disputed_for_section(broken, []) == []
    r1 = {"claim_a": "b claim", "claim_b": "x", "source_a_title": "A", "source_b_title": "B", "quote_a": "1", "quote_b": "2"}
    r2 = {"claim_a": "a claim", "claim_b": "y", "source_a_title": "C", "source_b_title": "D", "quote_a": "3", "quote_b": "4"}
    assert [d.claim_a for d in tiers.disputed_for_section([], [r1, r2])] == [d.claim_a for d in tiers.disputed_for_section([], [r2, r1])] == ["a claim", "b claim"]


# =========================================================================================================== references
PAPER = {"kind": "paper", "title": "Vision Transformers at Scale", "authors": ["Ada Lovelace", "Alan Turing"], "year": 2021, "venue": "NeurIPS",
         "doi": "10.1/abc", "arxiv_id": None, "pdf_url": None, "url": "https://doi.org/10.1/abc", "provider": "openalex", "published": "2021-05-01",
         "evidence_level": "full_text"}
WEB = {"kind": "web", "title": "Vision Transformers at Scale | Some Blog", "authors": [], "year": None, "venue": None, "doi": None, "arxiv_id": None, "pdf_url": None,
       "url": "https://www.Some-Blog.com/posts/vit?x=1", "provider": "tavily", "published": "March 2022", "evidence_level": "web_snippet"}


def E(sid, title, level="abstract", relation="supports"):
    return Evidence(source_id=sid, title=title, quote="q", relation=relation, evidence_level=level, ref_key=references.ref_key_of(title, sid))


def test_one_paper_under_two_source_ids_is_one_reference():
    p2 = dict(PAPER, authors=[], year=None, evidence_level="abstract")
    book = ReferenceBook({"id1": PAPER, "id2": p2})
    assert book.cite([E("id1", PAPER["title"]), E("id2", PAPER["title"])]) == [1]
    ref = book.references()[0]
    assert ref.source_ids == ["id1", "id2"] and ref.authors == ["Ada Lovelace", "Alan Turing"] and ref.year == 2021     # the richer row wins


def test_same_document_as_paper_and_web_is_one_reference_with_paper_metadata():
    book = ReferenceBook({"p": PAPER, "w": WEB})
    assert book.cite([E("p", PAPER["title"]), E("w", WEB["title"], level="web_snippet")]) == [1]
    ref = book.references()[0]
    assert ref.kind == "paper" and ref.venue == "NeurIPS" and ref.source_ids == ["p", "w"] and ref.url == "https://doi.org/10.1/abc"
    assert ref.evidence_level == "abstract"                                             # the best of the CITED entries (abstract and web snippet)


def test_missing_authors_year_venue_do_not_fail():
    bare = {"kind": "paper", "title": "Untold Story", "authors": None, "year": None, "venue": None, "doi": None, "arxiv_id": None, "pdf_url": None, "url": None}
    book = ReferenceBook({"x": bare})
    book.cite(E("x", "Untold Story"))
    ref = book.references()[0]
    assert (ref.authors, ref.year, ref.venue, ref.doi, ref.url) == ([], None, None, None, None)
    assert format_reference(ref) == "(n.d.). Untold Story."


def test_paper_url_follows_paper_service_rule_when_the_loader_left_it_out():
    meta = {"kind": "paper", "title": "T", "doi": None, "arxiv_id": "2010.11929", "pdf_url": "https://x/p.pdf"}
    book = ReferenceBook({"x": meta})
    book.cite(E("x", "T"))
    assert book.references()[0].url == "https://arxiv.org/abs/2010.11929"


def test_year_is_read_from_text_or_the_published_date():
    book = ReferenceBook({"a": {"kind": "paper", "title": "A paper", "year": "2019"}, "b": {"kind": "paper", "title": "B paper", "year": None, "published": "2020-03-04"},
                          "c": {"kind": "paper", "title": "C paper", "year": "n/a"}})
    for sid, t in (("a", "A paper"), ("b", "B paper"), ("c", "C paper")):
        book.cite(E(sid, t))
    assert [r.year for r in book.references()] == [2019, 2020, None]


def test_web_reference_domain_and_fields():
    book = ReferenceBook({"w": WEB})
    book.cite(E("w", WEB["title"], level="web_snippet"))
    ref = book.references()[0]
    assert (ref.kind, ref.domain, ref.published, ref.evidence_level) == ("web", "some-blog.com", "March 2022", "web_snippet")
    assert ref.authors == [] and ref.year is None and ref.title == WEB["title"]


def test_domain_of_edge_cases():
    assert domain_of("https://www.Example.COM:8080/a/b") == "example.com"
    assert domain_of("http://sub.example.org") == "sub.example.org"
    assert domain_of("example.com/path") == "example.com"
    assert domain_of("") is None and domain_of(None) is None and domain_of("http://") is None and domain_of(12) is None


def test_numbers_follow_the_order_of_first_citation():
    book = ReferenceBook({})
    assert book.cite([E("1", "Gamma"), E("2", "Alpha")]) == [1, 2]
    assert book.cite([E("3", "Beta"), E("4", "Gamma")]) == [1, 3]                       # Gamma keeps number 1, Beta gets the next free one
    assert [r.title for r in book.references()] == ["Gamma", "Alpha", "Beta"]
    assert [r.number for r in book.references()] == [1, 2, 3] and book.get(3).title == "Beta" and book.get(9) is None


def test_cite_a_claim_uses_supports_and_near_match_but_not_the_conflicting_side():
    claim = build([row("P", "partially_supported", [ev("a", "Alpha"), ev("b", "Beta", relation="near_match", near_claim="close"), ev("c", "Gamma", relation="contradicts")])])[0]
    book = ReferenceBook({})
    assert book.cite(claim) == [1, 2]
    assert [r.title for r in book.references()] == ["Alpha", "Beta"]
    assert book.cite(claim.conflicting()) == [3]                                         # a disagreement cites its other side explicitly
    assert book.cite([]) == [] and book.cite(None) == []


def test_cite_key_for_disagreement_sides_and_unknown_sources():
    book = ReferenceBook({"p": PAPER})
    n = book.cite_key("vision transformers at scale", title="ignored title")
    assert n == 1 and book.references()[0].authors == ["Ada Lovelace", "Alan Turing"]
    m = book.cite_key("mystery doc", title="Mystery Doc", source_id="zz")
    assert m == 2 and book.get(2).title == "Mystery Doc" and book.get(2).source_ids == ["zz"] and book.get(2).kind == "web"
    assert book.cite_key("nothing known").__class__ is int and book.get(3).title == references.UNTITLED


def test_evidence_level_is_the_best_cited_level():
    book = ReferenceBook({})
    book.cite([E("1", "Doc", level="web_snippet")])
    book.cite([E("2", "Doc", level="full_text")])
    book.cite([E("3", "Doc", level="abstract")])
    assert book.references()[0].evidence_level == "full_text" and book.references()[0].source_ids == ["1", "2", "3"]


def test_render_marker():
    assert render_marker([3, 1, 3]) == "[1, 3]" and render_marker([]) == "" and render_marker([7]) == "[7]"
    assert ReferenceBook.render_marker([2, 10]) == "[2, 10]" and render_marker(None) == ""


def test_format_reference_plain_and_markdown():
    p = Reference(number=1, ref_key="k", kind="paper", title="Deep Nets", authors=["A One", "B Two", "C Three", "D Four"], year=2020, venue="ICML",
                  doi="10.1/x", url="https://doi.org/10.1/x")
    assert format_reference(p) == "A One, B Two, C Three et al. (2020). Deep Nets. ICML. https://doi.org/10.1/x"
    assert format_reference(p, markdown=True) == "A One, B Two, C Three et al. (2020). *Deep Nets*. ICML. [https://doi.org/10.1/x](https://doi.org/10.1/x)"
    two = Reference(number=2, ref_key="k2", kind="paper", title="T", authors=["A One", "B Two"], year=2019)
    assert format_reference(two) == "A One and B Two (2019). T."
    w = Reference(number=3, ref_key="k3", kind="web", title="A Post", url="https://blog.example.com/p", domain="blog.example.com", published="2022-01-02")
    assert format_reference(w, accessed="2026-11-10") == "A Post. blog.example.com, 2022-01-02. https://blog.example.com/p (accessed 2026-11-10)"
    assert format_reference(Reference(number=4, ref_key="k4", kind="web", title="")) == "Untitled source."
    book = ReferenceBook({}, accessed="2026-11-10")
    assert "(accessed 2026-11-10)" in book.format_reference(w) and "accessed" not in book.format_reference(p)


def test_accessed_date_from_created_at():
    assert references.accessed_date("2026-11-10T18:30:00+05:30") == "2026-11-10"
    assert references.accessed_date(None) == "" and references.accessed_date("garbage") == ""


def test_reference_list_from_claims_end_to_end():
    claims = build([row("S", "supported", [ev("p", PAPER["title"], quote="q1"), ev("w", "Other web page", quote="q2", level="abstract")], 0.9)])
    book = ReferenceBook({"p": PAPER, "w": {"kind": "web", "title": "Other web page", "url": "https://other.org/a", "published": None}}, accessed="2026-11-10")
    nums = book.cite(claims[0])
    assert nums == [1, 2] and render_marker(nums) == "[1, 2]"
    lines = [book.format_reference(r) for r in book.references()]
    assert lines[0].startswith("Ada Lovelace and Alan Turing (2021). Vision Transformers at Scale. NeurIPS.") and lines[1].endswith("(accessed 2026-11-10)")


# ============================================================================================================== loader
class Query:
    def __init__(self, rows):
        self.rows, self.filters = rows, []

    def select(self, *_):
        return self

    def eq(self, col, val):
        self.filters.append(lambda r: r.get(col) == val)
        return self

    def in_(self, col, vals):
        self.filters.append(lambda r: r.get(col) in vals)
        return self

    def execute(self):
        return SimpleNamespace(data=[dict(r) for r in self.rows if all(f(r) for f in self.filters)])


class FakeDB:
    def __init__(self, **tables):
        self.tables = tables
        self.reads = []

    def table(self, name):
        self.reads.append(name)
        if name == "boom":
            raise RuntimeError("db down")
        return Query(self.tables.get(name, []))


QID = str(uuid.uuid4())
PID, PID2, WID = (str(uuid.uuid4()) for _ in range(3))


def db_fixture():
    sqs = [{"id": "sqB", "query_id": QID, "main_topic": "Second?", "detail_questions": '["d1", "d2"]', "created_at": "2026-11-10T10:00:05+00:00"},
           {"id": "sqA", "query_id": QID, "main_topic": "First?", "detail_questions": ["x"], "created_at": "2026-11-10T10:00:01+00:00"}]
    evid_a = [ev(PID, "Vision Transformers at Scale", "q1"), ev(PID2, "Another Paper", "q3")]
    facts = [dict(row("Claim A", "supported", evid_a, 0.9), sub_question_id="sqA", id="uuid-1", created_at="x"),
             dict(row("Claim B", "unverified", [ev(WID, "Vision Transformers at Scale | Some Blog", "q2", level="web_snippet", via="stage3_judge")], 0.4),
                  sub_question_id="sqB", id="uuid-2")]
    contras = [{"claim_a": "Claim A", "claim_b": "not A", "source_a_title": "Vision Transformers at Scale", "source_b_title": "Z", "quote_a": "q1", "quote_b": "qz",
                "prob": 0.7, "sub_question_id": "sqA"}]
    covs = [{"sub_question_id": "sqA", "created_at": "2026-11-10T10:30:00+00:00", "sufficient": False, "source_count": 3, "full_text_source_count": 1,
             "uncovered_details": ["Which datasets?"], "uncovered_aspects": ["dataset size"], "unjudged_aspects": [], "digest_failures": 2,
             "judge_stats": {"loop2": {"known_gaps_no_evidence": ["training cost"], "aspects": {"latency": {"status": "covered", "how": "synthesis"}}}}},
            {"sub_question_id": "sqA", "created_at": "2026-11-09T09:00:00+00:00", "sufficient": True, "uncovered_details": []},        # an older generation: ignored
            {"sub_question_id": "sqB", "created_at": "2026-11-10T10:31:00+00:00", "sufficient": True, "source_count": 2}]
    papers = [{"id": PID, "title": "Vision Transformers at Scale", "authors": ["Ada Lovelace"], "year": 2021, "venue": "NeurIPS", "doi": "10.1/abc", "arxiv_id": "2010.1",
               "pdf_url": None, "source": "openalex", "published_date": "2021-05-01"},
              {"id": PID2, "title": "Another Paper", "authors": None, "year": None, "venue": None, "doi": None, "arxiv_id": "2001.2", "pdf_url": None, "source": "arxiv"}]
    webs = [{"id": WID, "title": "Vision Transformers at Scale | Some Blog", "url": "https://some.blog/vit", "provider": "tavily", "published_date": "2022"}]
    digests = [{"sub_question_id": "sqA", "source_id": PID, "evidence_level": "full_text", "created_at": "2026-11-10T10:10:00+00:00"},
               {"sub_question_id": "sqA", "source_id": WID, "evidence_level": "web_snippet", "created_at": "2026-11-10T10:10:00+00:00"},
               {"sub_question_id": "sqB", "source_id": PID2, "evidence_level": "abstract", "created_at": "2026-11-10T10:12:00+00:00"}]
    return FakeDB(research_queries=[{"id": QID, "raw_query": "ViT vs CNN?", "created_at": "2026-11-10T10:00:00+00:00"}], sub_questions=sqs, coverage_results=covs,
                  fact_claims=facts, contradictions=contras, retrieved_papers=papers, web_sources=webs, digests=digests)


def test_load_inputs_from_database_shape_and_order():
    data = loader.load_inputs(QID, db=db_fixture())
    assert (data["query_id"], data["question"], data["created_at"]) == (QID, "ViT vs CNN?", "2026-11-10T10:00:00+00:00")
    assert [s["id"] for s in data["sub_questions"]] == ["sqA", "sqB"]                  # created_at order, not table order
    a, b = data["sub_questions"]
    assert (a["title"], b["detail_questions"]) == ("First?", ["d1", "d2"])             # jsonb text is parsed
    assert [r["claim"] for r in a["claims"]] == ["Claim A"] and "id" not in a["claims"][0] and a["claims"][0]["sub_question_id"] == "sqA"
    assert len(a["contradictions"]) == 1 and b["contradictions"] == []
    assert data["fact_ran"] is True and data["fact_error"] is None and data["domain_context"] == ""
    assert data["status_hints"]["origin"] == "db" and data["status_hints"]["found"] and data["status_hints"]["no_claims_sub_questions"] == []


def test_load_inputs_coverage_view_uses_the_newest_generation_and_collects_gaps():
    a, b = loader.load_inputs(QID, db=db_fixture())["sub_questions"]
    cov = a["coverage"]
    assert cov["present"] and cov["sufficient"] is False and cov["uncovered_details"] == ["Which datasets?"] and cov["uncovered_aspects"] == ["dataset size"]
    assert cov["known_gaps"] == ["training cost"] and cov["covered_by_synthesis"] == ["latency"] and cov["digest_failures"] == 2
    assert b["coverage"]["sufficient"] is True and b["coverage"]["known_gaps"] == []


def test_load_inputs_source_metadata_for_papers_and_web():
    src = loader.load_inputs(QID, db=db_fixture())["sources"]
    assert set(src) == {PID, PID2, WID}
    p = src[PID]
    assert (p["kind"], p["title"], p["authors"], p["year"], p["venue"], p["doi"], p["evidence_level"]) == ("paper", "Vision Transformers at Scale", ["Ada Lovelace"], 2021, "NeurIPS", "10.1/abc", "full_text")
    assert p["url"] == "https://doi.org/10.1/abc"                                       # paper_service's rule: doi first
    assert src[PID2]["url"] == "https://arxiv.org/abs/2001.2" and src[PID2]["authors"] == [] and src[PID2]["evidence_level"] == "abstract"
    assert (src[WID]["kind"], src[WID]["url"], src[WID]["provider"], src[WID]["published"], src[WID]["authors"]) == ("web", "https://some.blog/vit", "tavily", "2022", [])


def test_loaded_inputs_flow_through_tiers_and_references():
    data = loader.load_inputs(QID, db=db_fixture())
    claims = tiers.build_claims(data["sub_questions"])
    assert {c.text: c.tier for c in claims} == {"Claim A": TIER_SUPPORTED, "Claim B": TIER_SINGLE}
    book = ReferenceBook(data["sources"], accessed=references.accessed_date(data["created_at"]))
    assert book.cite(claims[0]) == [1, 2]
    assert book.cite(claims[1]) == [1]                                                  # the web page is the same document as paper 1: no new number
    ref = book.references()[0]
    assert ref.kind == "paper" and sorted(ref.source_ids) == sorted([PID, WID]) and ref.venue == "NeurIPS" and len(book.references()) == 2


def test_load_inputs_unknown_id_and_stage4_off():
    assert loader.load_inputs("nope", db=db_fixture())["status_hints"]["found"] is False
    db = db_fixture()
    db.tables["fact_claims"] = []
    data = loader.load_inputs(QID, db=db)
    assert data["fact_ran"] is False and data["status_hints"]["no_claims_sub_questions"] == ["sqA", "sqB"] and data["sources"] == {}


def test_load_inputs_uses_report_service_client_by_default(monkeypatch):
    monkeypatch.setattr(report_service, "supabase", db_fixture())
    data = loader.load_inputs(QID)
    assert len(data["sub_questions"]) == 2 and data["sources"][PID]["kind"] == "paper"


def test_load_inputs_retries_a_dropped_connection_once(monkeypatch):
    import httpx
    calls = {"n": 0}
    real = loader._load

    def flaky(qid, db):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.RemoteProtocolError("Server disconnected")
        return real(qid, db)
    monkeypatch.setattr(loader, "_load", flaky)
    monkeypatch.setattr("apps.api.services.db_errors.time.sleep", lambda s: None)
    assert loader.load_inputs(QID, db=db_fixture())["status_hints"]["found"] and calls["n"] == 2


# ---------------------------------------------------------------------------------------------------------------- from_state
def state_fixture(**over):
    plan = SimpleNamespace(query_id=QID, raw_query="ViT vs CNN?", domain_anchor="deep learning", domain_context="Comparing image models.",
                           sub_questions=[SimpleNamespace(id="sqA", main_topic="First?", detail_questions=["x"], queries=["q"]),
                                          {"id": "sqB", "main_topic": "Second?", "detail_questions": ["d1"]}])
    fact_claims = [dict(row("Claim A", "supported", [ev(PID, "Vision Transformers at Scale", "q1"), ev(PID2, "Another Paper", "q3")]), sub_question_id="sqA"),
                   dict(row("Claim B", "unverified", [ev(WID, "Web page", "q2", level="web_snippet")]), sub_question_id="sqB")]
    state = {"raw_query": "ViT vs CNN?", "query_id": QID, "task_plan": plan, "fact_claims": fact_claims,
             "fact_summary": {"sqA": {"judge_failures": 2, "supported": 1}, "sqB": {"error": "boom"}},
             "coverage": {"sqA": {"sufficient": True, "uncovered_details": ["Which datasets?"], "source_count": 2}},
             "digests": [{"source_id": PID, "evidence_level": "full_text"}], "contradictions": [{"claim_a": "Claim A", "claim_b": "n", "sub_question_id": "sqA"}]}
    state.update(over)
    return state


def test_from_state_builds_the_same_shape():
    db = db_fixture()
    data = loader.from_state(state_fixture(), db=db)
    assert [s["id"] for s in data["sub_questions"]] == ["sqA", "sqB"] and data["domain_context"] == "Comparing image models." and data["domain_anchor"] == "deep learning"
    a, b = data["sub_questions"]
    assert a["coverage"]["uncovered_details"] == ["Which datasets?"] and b["coverage"]["present"] is False
    assert len(a["contradictions"]) == 1 and a["fact_summary"]["judge_failures"] == 2 and b["fact_error"] == "boom" and a["fact_error"] is None
    assert data["fact_ran"] is True and data["fact_error"] is None and data["created_at"] == "2026-11-10T10:00:00+00:00"
    assert data["sources"][PID]["evidence_level"] == "full_text" and data["sources"][PID]["kind"] == "paper" and data["sources"][WID]["kind"] == "web"
    h = data["status_hints"]
    assert (h["origin"], h["fact_failed_sub_questions"], h["coverage_missing"], h["judge_failures"]) == ("state", ["sqB"], ["sqB"], 2)
    assert "contradictions" not in db.reads                                              # taken from the state, not the database


def test_from_state_accepts_an_object_state_and_reads_missing_contradictions_from_the_database():
    s = state_fixture()
    s.pop("contradictions")
    obj = SimpleNamespace(**s)
    data = loader.from_state(obj, db=db_fixture())
    assert len(data["sub_questions"][0]["contradictions"]) == 1                          # the fixture database holds one row for sqA


def test_from_state_whole_stage_failure_and_stage_off():
    data = loader.from_state(state_fixture(fact_claims=[], fact_summary={"error": "judge down"}), db=db_fixture())
    assert data["fact_ran"] is False and data["fact_error"] == "judge down" and data["status_hints"]["no_claims_sub_questions"] == ["sqA", "sqB"]
    off = loader.from_state(state_fixture(fact_claims=[], fact_summary={}), db=db_fixture())
    assert off["fact_ran"] is False and off["fact_error"] is None


def test_from_state_survives_a_database_failure_without_metadata():
    class Down(FakeDB):
        def table(self, name):
            raise RuntimeError("db down")
    data = loader.from_state(state_fixture(), db=Down())
    assert data["sources"] == {} and data["status_hints"]["sources_without_metadata"] == 3 and len(data["sub_questions"]) == 2
    book = ReferenceBook(data["sources"])
    claims = tiers.build_claims(data["sub_questions"])
    assert book.cite(claims[0]) and book.references()[0].title                          # the reference list falls back to the evidence titles


def test_from_state_created_at_argument_skips_the_lookup():
    db = db_fixture()
    data = loader.from_state(state_fixture(), db=db, created_at="2026-01-02T00:00:00")
    assert data["created_at"] == "2026-01-02T00:00:00" and "research_queries" not in db.reads


def test_coverage_view_handles_missing_and_odd_values():
    assert loader.coverage_view(None)["present"] is False and loader.coverage_view({})["present"] is False
    v = loader.coverage_view({"sufficient": 1, "uncovered_details": '["a", "", 3]', "digest_failures": ["x", "y"], "judge_stats": "not a dict", "fallback_reason": ""})
    assert (v["present"], v["sufficient"], v["uncovered_details"], v["digest_failures"], v["known_gaps"], v["fallback_reason"]) == (True, True, ["a"], 2, [], None)


def test_two_partly_claims_that_are_each_others_near_match_are_reported_once():
    rows = [row("CNNs are black boxes", "partially_supported", [ev("a", "Alpha"), ev("b", "Beta", relation="near_match", near_claim="Backprop models are black-box")], 0.7),
            row("Backprop models are black-box", "partially_supported", [ev("b", "Beta"), ev("a", "Alpha", relation="near_match", near_claim="CNNs are black boxes")], 0.6),
            row("Another partly claim", "partially_supported", [ev("c", "Gamma"), ev("d", "Delta", relation="near_match", near_claim="close")], 0.5)]
    got = by_text(build(rows))
    assert got["CNNs are black boxes"].tier == TIER_PARTLY and got["Another partly claim"].tier == TIER_PARTLY
    assert got["Backprop models are black-box"].tier is None and got["Backprop models are black-box"].filtered_reason == tiers.FILTER_MIRROR
