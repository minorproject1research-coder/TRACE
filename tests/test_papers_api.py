"""Paper views of a run (services/paper_service.py, routers/paper_router.py). Offline: no database, no graph."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.api.dependencies import get_run_manager  # noqa: E402
from apps.api.main import app  # noqa: E402
from apps.api.services import paper_service as ps, run_manager as rm  # noqa: E402

TEXT = (
    "## Abstract\n\nMixture-of-Experts models route each token to a small subset of experts [4]. Load balancing is usually enforced "
    "with an auxiliary loss that penalises uneven expert use.\n\n## 1 Introduction\n\nThe router is a learned linear layer; "
    "its top-k choice is not always the best route for a token (see Fig. 1)."
)


def cut(text, span):
    return text[span["start"]:span["end"]]


def test_locates_exact_quote_and_returns_its_text():
    spans = ps.QuoteLocator(TEXT).locate("Load balancing is usually enforced with an auxiliary loss")
    assert len(spans) == 1
    assert cut(TEXT, spans[0]).lower().startswith("load balancing is usually enforced with an auxiliary loss")


def test_citation_markers_hyphenation_and_case_do_not_prevent_a_match():
    q = "mixture-of-experts models route each token to a small subset of experts"
    spans = ps.QuoteLocator(TEXT).locate(q)
    assert len(spans) == 1 and "small subset of experts" in cut(TEXT, spans[0])
    hyph = "Load balan-\ncing is usually enforced with an auxiliary loss"          # a PDF line-break hyphen inside the *text* is removed too
    text2 = TEXT.replace("Load balancing", "Load balan-\ncing")
    s2 = ps.QuoteLocator(text2).locate(hyph)
    assert len(s2) == 1 and cut(text2, s2[0]).startswith("Load balan-\ncing")


def test_quote_with_an_elision_gives_one_span_per_piece():
    q = "The router is a learned linear layer [...] its top-k choice is not always the best route for a token"
    spans = ps.QuoteLocator(TEXT).locate(q)
    assert len(spans) == 2 and spans[0]["end"] <= spans[1]["start"]


def test_quote_that_is_not_in_the_text_gets_no_span():
    assert ps.QuoteLocator(TEXT).locate("Experts are always selected uniformly at random during training of the model") == []
    assert ps.QuoteLocator(TEXT).locate("too short") == []
    assert ps.QuoteLocator("").locate("anything long enough to be a real quote here") == []


def test_offsets_are_utf16_so_they_line_up_with_javascript_strings():
    text = "Intro \U0001D465 and \U0001D466 are variables. The router selects the top two experts for every single token in the batch."
    spans = ps.QuoteLocator(text).locate("The router selects the top two experts for every single token")
    assert len(spans) == 1
    js_text = text.encode("utf-16-le")                                              # what a browser indexes into
    got = js_text[spans[0]["start"] * 2:spans[0]["end"] * 2].decode("utf-16-le")
    assert got.startswith("The router selects the top two experts")


# ---------------------------------------------------------------------------------------------------------------- endpoints
@pytest.fixture
def client(monkeypatch):
    manager = rm.RunManager(graph_factory=lambda: None, max_workers=1, max_pending=1)
    app.dependency_overrides[get_run_manager] = lambda: manager
    c = TestClient(app)
    c.manager = manager
    yield c
    app.dependency_overrides.clear()
    manager.shutdown()


def test_unknown_run_is_404(client, monkeypatch):
    monkeypatch.setattr(ps, "build_papers_overview", lambda qid: None)
    assert client.get("/api/research/nope/papers").status_code == 404


def test_a_queued_run_without_database_rows_has_an_empty_funnel(client, monkeypatch):
    monkeypatch.setattr(ps, "build_papers_overview", lambda qid: None)
    monkeypatch.setattr(client.manager, "get", lambda rid: object())
    r = client.get("/api/research/abc/papers")
    assert r.status_code == 200 and r.json()["counts"]["papersKept"] == 0 and r.json()["papers"] == []


def test_overview_and_detail_are_passed_through(client, monkeypatch):
    monkeypatch.setattr(ps, "build_papers_overview", lambda qid: {"id": qid, "counts": {"papersKept": 2}, "papers": [], "web": [], "subQuestions": []})
    monkeypatch.setattr(ps, "build_paper_detail", lambda qid, pid: {"paper": {"id": pid}} if pid == "p1" else None)
    assert client.get("/api/research/q/papers").json()["counts"]["papersKept"] == 2
    assert client.get("/api/research/q/papers/p1").json()["paper"]["id"] == "p1"
    assert client.get("/api/research/q/papers/zzz").status_code == 404


def test_a_malformed_paper_id_is_not_sent_to_the_database(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("database must not be queried for an invalid id")
    monkeypatch.setattr(ps.supabase, "table", boom)
    assert ps.build_paper_detail("q", "not-a-uuid") is None
