"""The written report as the web app gets it: the evidence behind every sentence, a link from every citation to the parsed paper, and the answer as parts
(services/written_report_links.py), plus the finding ids of the paper page. Offline: the database is a small fake."""
import copy
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.api.agents.stage5_report import tiers  # noqa: E402
from apps.api.agents.stage5_report.schema import make_claim_id  # noqa: E402
from apps.api.dependencies import get_run_manager  # noqa: E402
from apps.api.main import app  # noqa: E402
from apps.api.services import db_errors, db_service, paper_service as ps, report_service, run_manager as rm, written_report_links as wl  # noqa: E402

REAL_LOAD_CONTEXT = wl.load_context                  # the conftest replaces it for every test; the tests of the loader need the real one

QID = "aaaaaaaa-0000-0000-0000-000000000001"
P1A, P1B, P2 = "11111111-0000-0000-0000-00000000000a", "11111111-0000-0000-0000-00000000000b", "22222222-0000-0000-0000-000000000002"
W3 = "33333333-0000-0000-0000-000000000003"
Q1 = "Federated learning reaches accuracy comparable to centralized training."
Q2 = "Differential privacy lowers the accuracy by 2.7 % on noisy data."


def cid(sq, text):
    return make_claim_id(sq, text)


def sentence(text, claims, refs, tier="partly", origin="llm"):
    return {"text": text, "claimIds": claims, "refs": refs, "tier": tier, "origin": origin}


def a_report():
    c1, c2, c3, c4, c5 = (cid("sq1", "claim one"), cid("sq1", "claim two"), cid("sq1", "claim three"), cid("sq2", "claim four"), cid("sq2", "claim five"))
    return {
        "status": "completed_with_warnings", "question": "How does federated learning compare?",
        "overview": {"counts": {"documents": 5, "claims": 9, "disagreements": 1},
                     "summary": [sentence("Federated learning matches centralized accuracy of about 35%.", [c1], [1, 2]),
                                 sentence("Differential privacy costs 2.7 % accuracy.", [c4], [3], tier="single"),
                                 sentence("The evidence collected does not settle: how does it scale; what happens under non-IID data.", [], [], tier="note", origin="template")]},
        "sections": [
            {"id": "s1", "title": "Accuracy", "subQuestionId": "sq1", "detailQuestions": [], "gaps": [], "disagreements": [],
             "sentences": [sentence("Claim one sentence.", [c1], [1, 2]), sentence("Claim two sentence.", [c2], [1], tier="supported"), sentence("Claim three sentence.", [c3], [2], tier="single")]},
            {"id": "s2", "title": "Privacy", "subQuestionId": "sq2", "detailQuestions": [], "gaps": ["gap"],
             "disagreements": [{"claimA": "A says up", "claimB": "B says down", "sideA": {"ref": 1, "quote": "q"}, "sideB": {"ref": 3, "quote": "q"}}],
             "sentences": [sentence("Claim four sentence.", [c4], [3], tier="single"), sentence("Claim five sentence.", [c5], [2], tier="partly")]},
        ],
        "conclusion": [sentence("Bottom line sentence.", [c2], [1], tier="supported")],
        "references": [{"number": 1, "title": "Paper one", "kind": "paper", "evidenceLevel": "full_text", "sourceIds": [P1A, P1B]},
                       {"number": 2, "title": "Paper two", "kind": "paper", "evidenceLevel": "abstract", "sourceIds": [P2]},
                       {"number": 3, "title": "A web page", "kind": "web", "evidenceLevel": "web_snippet", "sourceIds": [W3]}],
        "limitations": [], "warnings": [],
    }


def a_context():
    ev = lambda sid, quote, rel="supports", level="full_text": {"sourceId": sid, "quote": quote, "relation": rel, "level": level}      # noqa: E731
    claims = {
        cid("sq1", "claim one"): {"subQuestionId": "sq1", "evidence": [ev(P1A, Q1), ev(P2, "Another quote from paper two.", "near_match", "abstract"), ev(P1A, "Contradicting quote.", "contradicts")]},
        cid("sq1", "claim two"): {"subQuestionId": "sq1", "evidence": [ev(P1B, "Quote of claim two from the second copy of paper one.")]},
        cid("sq1", "claim three"): {"subQuestionId": "sq1", "evidence": [ev(P2, "Quote of claim three.")]},
        cid("sq2", "claim four"): {"subQuestionId": "sq2", "evidence": [ev(W3, Q2, level="web_snippet")]},
        cid("sq2", "claim five"): {"subQuestionId": "sq2", "evidence": [ev(P2, "Quote of claim five.")]},
    }
    return wl.Context(claims, papers={P1A, P1B, P2}, parsed={P1A, P1B})        # paper two is a paper that was not parsed; the web page is not a paper


# ---------------------------------------------------------------------------------------------------------------------------- citations
def test_a_citation_holds_the_quotes_behind_the_sentence_grouped_by_reference():
    out = wl.enrich_report(a_report(), a_context())
    first = out["overview"]["summary"][0]
    assert [c["ref"] for c in first["citations"]] == [1, 2]
    by_ref = {c["ref"]: c for c in first["citations"]}
    assert [q["text"] for q in by_ref[1]["quotes"]] == [Q1], "the contradicting quote of the claim is not cited"
    assert by_ref[1]["quotes"][0]["findingId"] == ps.finding_id(Q1) and by_ref[1]["quotes"][0]["relation"] == "supports"
    assert by_ref[2]["quotes"][0]["relation"] == "near_match" and by_ref[2]["quotes"][0]["evidenceLevel"] == "abstract"
    assert {c["ref"] for s in wl._sentences(out) for c in s["citations"]} == {1, 2, 3}


def test_the_citations_of_a_sentence_are_the_references_it_cites():
    out = wl.enrich_report(a_report(), a_context())
    for s in wl._sentences(out):
        assert {c["ref"] for c in s["citations"]} == set(s["refs"]), s["text"]


def test_a_note_and_a_sentence_without_known_claims_get_an_empty_list():
    report = a_report()
    report["sections"][0]["sentences"].append(sentence("Unknown claim.", ["c_0000000000"], [2]))
    out = wl.enrich_report(report, a_context())
    assert out["overview"]["summary"][2]["citations"] == [] and out["sections"][0]["sentences"][-1]["citations"] == []


def test_at_most_three_distinct_quotes_per_citation():
    ctx = a_context()
    ctx.claims[cid("sq1", "claim one")]["evidence"] += [{"sourceId": P1A, "quote": f"Extra quote number {i}.", "relation": "supports", "level": "full_text"} for i in range(5)]
    ctx.claims[cid("sq1", "claim one")]["evidence"].append({"sourceId": P1A, "quote": "  federated   LEARNING reaches accuracy comparable to centralized training.", "relation": "supports", "level": "full_text"})
    quotes = {c["ref"]: c for c in wl.enrich_report(a_report(), ctx)["overview"]["summary"][0]["citations"]}[1]["quotes"]
    assert len(quotes) == 3 and len({q["findingId"] for q in quotes}) == 3


def test_a_citation_links_to_the_paper_that_holds_its_quote():
    out = wl.enrich_report(a_report(), a_context())
    claim_two = out["sections"][0]["sentences"][1]["citations"][0]
    assert claim_two["ref"] == 1 and claim_two["paperId"] == P1B and claim_two["parsed"] is True      # the second copy of paper one, not the reference's first
    assert claim_two["quotes"][0]["paperId"] == P1B
    unparsed = out["sections"][0]["sentences"][2]["citations"][0]
    assert unparsed["paperId"] == P2 and unparsed["parsed"] is False and unparsed["quotes"][0]["parsed"] is False


def test_a_web_source_has_no_paper_to_open():
    out = wl.enrich_report(a_report(), a_context())
    web = out["overview"]["summary"][1]["citations"][0]
    assert web["ref"] == 3 and web["paperId"] is None and web["parsed"] is False and web["quotes"][0]["paperId"] is None


def test_a_reference_names_the_paper_to_open_and_how_often_it_is_cited():
    out = wl.enrich_report(a_report(), a_context())
    refs = {r["number"]: r for r in out["references"]}
    assert refs[1]["paper"] == {"id": P1A, "parsed": True}, "of the copies of a document the parsed one that is cited most, then the smaller id"
    assert refs[2]["paper"] == {"id": P2, "parsed": False} and refs[3]["paper"] is None
    assert refs[1]["citedIn"] == 4 and refs[3]["citedIn"] == 2        # ref 1: the answer, two sentences of "Accuracy", the conclusion; ref 3: the answer and one sentence of "Privacy"


def test_a_reference_prefers_the_parsed_copy():
    ctx = a_context()
    ctx.parsed = {P1B}
    assert {r["number"]: r for r in wl.enrich_report(a_report(), ctx)["references"]}[1]["paper"] == {"id": P1B, "parsed": True}


def test_the_stored_report_is_not_changed_and_enriching_twice_gives_the_same():
    report = a_report()
    before = copy.deepcopy(report)
    once = wl.enrich_report(report, a_context())
    assert report == before
    assert wl.enrich_report(once, a_context()) == once


def test_every_field_of_the_stored_report_survives():
    report = a_report()
    out = wl.enrich_report(report, a_context())
    for s_in, s_out in zip(wl._sentences(report), wl._sentences(out)):
        assert {k: v for k, v in s_out.items() if k != "citations"} == s_in
    assert out["overview"]["counts"] == report["overview"]["counts"] and out["overview"]["summary"][0]["text"] == report["overview"]["summary"][0]["text"]


def test_a_surprising_shape_does_not_raise():
    assert wl.enrich_report({}, wl.Context()) == {}
    odd = {"overview": {"summary": ["not a dict", {"text": "x"}]}, "sections": [{"id": "a"}], "references": [{"number": "1"}, None, {"number": 2, "sourceIds": None}], "conclusion": None}
    out = wl.enrich_report(odd, wl.Context())
    assert out["overview"]["answer"]["parts"] == []


# --------------------------------------------------------------------------------------------------------------------------- the answer
def test_the_answer_is_built_part_by_part_from_the_sections_the_sentences_come_from():
    answer = wl.enrich_report(a_report(), a_context())["overview"]["answer"]
    assert answer["headline"] == {"sentenceIndex": 0}
    assert [(p["sectionId"], p["title"], p["sentenceIndex"]) for p in answer["parts"]] == [("s1", "Accuracy", 0), ("s2", "Privacy", 1)]
    assert answer["parts"][0]["sentence"]["citations"][0]["ref"] == 1, "the answer sentence carries its citations"


def test_a_part_offers_the_other_sentences_of_its_section_strongest_first_and_never_twice():
    parts = wl.enrich_report(a_report(), a_context())["overview"]["answer"]["parts"]
    assert [s["text"] for s in parts[0]["supporting"]] == ["Claim two sentence.", "Claim three sentence."]      # supported before single; "Claim one" is the answer itself
    assert [s["text"] for s in parts[1]["supporting"]] == ["Claim five sentence."]                              # "Claim four" is the answer itself
    assert all(s["citations"] for p in parts for s in p["supporting"])
    used = [c for p in parts for s in [p["sentence"], *p["supporting"]] for c in s["claimIds"]]
    assert len(used) == len(set(used)), "no claim appears in two places of the answer"


def test_the_strength_of_the_answer_is_counted_from_its_sentences():
    st = wl.enrich_report(a_report(), a_context())["overview"]["answer"]["strength"]
    assert st["statements"] == 2 and st["byTier"] == {"supported": 0, "partly": 1, "single": 1} and st["documents"] == 3 and st["fullTextDocuments"] == 1
    assert st["documentsInReport"] == 5 and st["partsCovered"] == 2 and st["sections"] == 2 and st["disagreements"] == 1 and st["openQuestions"] == 2
    assert st["line"] == ("2 statements from 3 documents; 1 partly supported; 1 from a single source, not confirmed; 1 disagreement between sources in the report; 2 open questions.")


def test_the_line_uses_singular_and_leaves_out_what_is_zero():
    report = a_report()
    report["overview"]["summary"] = [report["overview"]["summary"][0]]
    for sec in report["sections"]:
        sec["disagreements"] = []
    line = wl.enrich_report(report, a_context())["overview"]["answer"]["strength"]["line"]
    assert line == "1 statement from 2 documents; 1 partly supported."


def test_figures_are_the_percentages_of_the_answer_sentences():
    figures = wl.enrich_report(a_report(), a_context())["overview"]["answer"]["figures"]
    assert figures == [{"value": "35%", "sentenceIndex": 0, "refs": [1, 2]}, {"value": "2.7%", "sentenceIndex": 1, "refs": [3]}]


def test_the_open_questions_are_read_from_the_template_line_and_the_disputes_from_the_sections():
    answer = wl.enrich_report(a_report(), a_context())["overview"]["answer"]
    assert answer["openQuestions"] == ["how does it scale", "what happens under non-IID data"]
    assert answer["disputes"]["count"] == 1 and answer["disputes"]["items"] == [{"sectionId": "s2", "title": "Privacy", "claimA": "A says up", "claimB": "B says down", "refs": [1, 3]}]


def test_no_answer_sentence_means_no_answer_block():
    report = a_report()
    report["overview"]["summary"] = []
    assert "answer" not in wl.enrich_report(report, a_context())["overview"]
    assert "overview" not in wl.enrich_report({"sections": []}, wl.Context())


# --------------------------------------------------------------------------------------------------------------- the same ids as Stage 5
def test_claim_ids_are_the_ones_stage_5_made():
    row = {"claim": "  Federated learning  reaches accuracy. ", "label": "partially_supported", "evidence": [], "support_doc_count": 1}
    claim = tiers.claim_from_row("sq1", row)
    assert claim.claim_id == make_claim_id("sq1", wl._norm(row["claim"]))


# ---------------------------------------------------------------------------------------------------------------------------- the loader
class FakeTable:
    def __init__(self, rows):
        self.rows, self._filters = rows, []

    def select(self, *_):
        return self

    def eq(self, col, val):
        t = FakeTable(self.rows); t._filters = self._filters + [(col, {val})]; return t

    def in_(self, col, vals):
        t = FakeTable(self.rows); t._filters = self._filters + [(col, set(vals))]; return t

    def execute(self):
        return SimpleNamespace(data=[r for r in self.rows if all(r.get(c) in v for c, v in self._filters)])


class FakeDb:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return FakeTable(self.tables.get(name, []))


def test_the_loader_reads_the_claims_and_the_paper_state(monkeypatch):
    tables = {"fact_claims": [{"sub_question_id": "sq1", "claim": "claim  one", "evidence": [{"source_id": P1A, "quote": " Q  one ", "relation": "supports", "evidence_level": "full_text"},
                                                                                              {"source_id": "", "quote": "no source"}, {"source_id": P2, "quote": ""}, "junk"]},
                              {"sub_question_id": "sq1", "claim": "", "evidence": []}],
              "retrieved_papers": [{"id": P1A}], "parsed_papers": [{"retrieved_paper_id": P1A}]}
    monkeypatch.setattr(report_service, "supabase", FakeDb(tables))
    monkeypatch.setattr(wl, "_select_light", lambda table, cols, col, vals: [r for r in tables.get(table, []) if r.get(col) in vals])
    report = {"sections": [{"subQuestionId": "sq1"}], "references": [{"sourceIds": [P1A, W3, "not-a-uuid"]}]}
    ctx = REAL_LOAD_CONTEXT(report)
    assert list(ctx.claims) == [make_claim_id("sq1", "claim one")]
    assert ctx.claims[make_claim_id("sq1", "claim one")]["evidence"] == [{"sourceId": P1A, "quote": "Q one", "relation": "supports", "level": "full_text"}]
    assert ctx.papers == {P1A} and ctx.parsed == {P1A}


def test_a_report_without_sections_reads_nothing(monkeypatch):
    monkeypatch.setattr(report_service, "supabase", SimpleNamespace(table=lambda name: pytest.fail("no database read expected")))
    ctx = REAL_LOAD_CONTEXT({"sections": [], "references": []})
    assert ctx.claims == {} and ctx.papers == set()


# ----------------------------------------------------------------------------------------------------------------------------- the route
ROW = {"query_id": QID, "status": "completed_with_warnings", "report": a_report(), "markdown": "# Report", "stats": {}, "model": "m", "template_version": "s5-v3",
       "created_at": "2026-11-16T10:00:00+00:00", "updated_at": "2026-11-16T10:05:00+00:00"}


@pytest.fixture
def client(monkeypatch):
    manager = rm.RunManager(graph_factory=lambda: None, max_workers=1)
    app.dependency_overrides[get_run_manager] = lambda: manager
    monkeypatch.setattr(db_errors, "RETRY_DELAY_SECONDS", 0)
    monkeypatch.setattr(db_service, "get_written_report", lambda qid: ROW)
    yield TestClient(app)
    app.dependency_overrides.clear()
    manager.shutdown()


def test_the_route_returns_the_report_with_citations_and_answer_parts(client, monkeypatch):
    monkeypatch.setattr(wl, "load_context", lambda report: a_context())
    body = client.get(f"/api/research/{QID}/written-report").json()
    assert body["markdown"] == "# Report" and body["templateVersion"] == "s5-v3"
    assert body["report"]["overview"]["answer"]["parts"][0]["title"] == "Accuracy"
    assert body["report"]["overview"]["summary"][0]["citations"][0]["quotes"][0]["findingId"] == ps.finding_id(Q1)
    assert body["report"]["references"][0]["paper"]["id"] == P1A


def test_a_failure_of_the_extras_never_loses_the_report(client, monkeypatch):
    def broken(report):
        raise RuntimeError("boom")
    monkeypatch.setattr(wl, "load_context", broken)
    r = client.get(f"/api/research/{QID}/written-report")
    assert r.status_code == 200 and r.json()["report"] == ROW["report"] and r.json()["markdown"] == "# Report"


def test_a_dropped_connection_while_reading_the_extras_gives_the_stored_report(client, monkeypatch):
    def down(report):
        raise httpx.RemoteProtocolError("Server disconnected")
    monkeypatch.setattr(wl, "load_context", down)
    r = client.get(f"/api/research/{QID}/written-report")
    assert r.status_code == 200 and r.json()["report"] == ROW["report"]


# ---------------------------------------------------------------------------------------------------------------------------- the paper page
def test_a_finding_id_does_not_depend_on_spacing_or_case_and_differs_between_quotes():
    assert ps.finding_id("Federated  learning\nreaches accuracy.") == ps.finding_id(" federated learning reaches ACCURACY. ")
    assert ps.finding_id("one quote") != ps.finding_id("another quote") and ps.finding_id("").startswith("f_")


def test_the_findings_of_the_paper_page_have_the_id_the_citations_use(monkeypatch):
    quote = "federated learning reaches accuracy comparable to centralized training"
    text = f"# Title\n\nSome text. {quote}. More text.\n"
    tables = {
        "retrieved_papers": [{"id": P1A, "query_id": QID, "title": "Paper one", "sub_question_id": "sq1"}],
        "sub_questions": [{"id": "sq1", "query_id": QID, "main_topic": "Accuracy", "created_at": "2026-11-16T10:00:00+00:00"}],
        "digests": [{"source_id": P1A, "sub_question_id": "sq1", "created_at": "2026-11-16T10:01:00+00:00", "evidence_level": "full_text",
                     "findings": [{"claim": "FL is as accurate", "quote": quote.capitalize() + ".", "verified": True, "stance": "supports", "judge": {}}]}],
        "parsed_papers": [{"retrieved_paper_id": P1A, "full_text": text, "parser_version": 3, "sections": [], "figures": [], "cited_references": []}],
    }
    fake = FakeDb(tables)
    monkeypatch.setattr(ps, "supabase", fake)
    monkeypatch.setattr(report_service, "supabase", fake)
    detail = ps.build_paper_detail(QID, P1A)
    finding = detail["findings"][0]
    assert finding["id"] == ps.finding_id(quote.capitalize() + ".") == ps.finding_id(quote + ".")
    assert finding["spans"], "the quote is located in the parsed text"
    ctx = wl.Context({cid("sq1", "claim one"): {"subQuestionId": "sq1", "evidence": [{"sourceId": P1A, "quote": quote + ".", "relation": "supports", "level": "full_text"}]}}, {P1A}, {P1A})
    report = {"sections": [{"id": "s1", "title": "Accuracy", "subQuestionId": "sq1", "sentences": [sentence("FL is as accurate.", [cid("sq1", "claim one")], [1], tier="supported")]}],
              "references": [{"number": 1, "kind": "paper", "sourceIds": [P1A]}], "overview": {"summary": []}}
    citation = wl.enrich_report(report, ctx)["sections"][0]["sentences"][0]["citations"][0]
    assert citation["paperId"] == P1A and citation["quotes"][0]["findingId"] == finding["id"]
