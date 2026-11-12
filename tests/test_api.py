"""The API (apps/api/main.py): sessions, progress events, report. Offline: a fake graph and a fake database."""
import json
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.api.dependencies import get_run_manager  # noqa: E402
from apps.api.main import app  # noqa: E402
from apps.api.services import report_service, run_manager as rm  # noqa: E402

QUESTION = "How do state space models compare with transformers in training efficiency?"


class FakeGraph:
    """Yields what the real graph yields with stream_mode='updates'."""
    def __init__(self, error=None, gate=None):
        self.error, self.gate = error, gate

    def stream(self, state, stream_mode):
        assert stream_mode == "updates" and state.raw_query and state.query_id
        if self.gate:
            self.gate.wait(5)
        sq = SimpleNamespace(main_topic="What are SSMs?", queries=["a", "b"])
        yield {"planner": {"task_plan": SimpleNamespace(sub_questions=[sq, sq], domain_anchor="deep learning")}}
        yield {"paper_retrieval": {"paper_results": [{}, {}, {}]}}
        yield {"web_search": {"web_sources": [{}, {}]}}
        if self.error:
            raise self.error
        yield {"summarizer": {"digests": [1, 2, 3], "coverage": {"a": {"sufficient": True}, "b": {"sufficient": False}}}}


def make_manager(**kw):
    graph = kw.pop("graph", FakeGraph())
    return rm.RunManager(graph_factory=lambda: graph, **kw)


@pytest.fixture
def client(monkeypatch):
    manager = make_manager(max_workers=1, max_pending=3)
    app.dependency_overrides[get_run_manager] = lambda: manager
    monkeypatch.setattr(report_service, "session_from_db", lambda qid: None)
    monkeypatch.setattr(report_service, "build_report", lambda qid: None)
    monkeypatch.setattr(report_service, "list_sessions", lambda limit=20: [])
    c = TestClient(app)
    c.manager = manager
    yield c
    app.dependency_overrides.clear()
    manager.shutdown()


def wait_finished(manager, run_id, seconds=5):
    deadline = time.time() + seconds
    while time.time() < deadline:
        rec = manager.get(run_id)
        if rec and rec.finished:
            return rec
        time.sleep(0.02)
    raise AssertionError("run did not finish")


def read_events(client, run_id, headers=None, query=""):
    events = []
    with client.stream("GET", f"/api/research/{run_id}/events{query}", headers=headers or {}) as r:
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
        for line in r.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


# ------------------------------------------------------------------------------------------------------------------ sessions
def test_start_a_run_and_read_its_status(client):
    r = client.post("/api/research", json={"question": QUESTION})
    assert r.status_code == 202 and r.headers["location"] == f"/api/research/{r.json()['id']}"
    body = r.json()
    assert body["question"] == QUESTION and "options" not in body
    wait_finished(client.manager, body["id"])
    done = client.get(f"/api/research/{body['id']}").json()
    assert done["status"] == "completed" and done["error"] is None
    assert done["stages"] == {"planner": "completed", "retrieval": "completed", "summarizer": "completed", "factcheck": "not_run", "report": "not_run"}


def test_the_question_is_validated_and_tidied(client):
    assert client.post("/api/research", json={"question": "too short"}).status_code == 422
    assert client.post("/api/research", json={"question": "x" * 1001}).status_code == 422
    assert client.post("/api/research", json={}).status_code == 422
    r = client.post("/api/research", json={"question": f"  How   do SSMs\n compare with   transformers?  "})
    assert r.json()["question"] == "How do SSMs compare with transformers?"


def test_fields_an_older_client_may_still_send_are_ignored(client):
    r = client.post("/api/research", json={"question": QUESTION, "depth": "deep", "scope": "papers"})      # depth and scope were removed
    assert r.status_code == 202 and "options" not in r.json()


def test_the_run_id_reaches_the_graph_as_the_query_id(client):
    seen = {}

    class Spy(FakeGraph):
        def stream(self, state, stream_mode):
            seen["query_id"] = state.query_id
            return super().stream(state, stream_mode)
    manager = make_manager(graph=Spy(), max_workers=1)
    app.dependency_overrides[get_run_manager] = lambda: manager
    run_id = TestClient(app).post("/api/research", json={"question": QUESTION}).json()["id"]
    wait_finished(manager, run_id)
    assert seen["query_id"] == run_id
    manager.shutdown()


def test_a_full_queue_answers_429(monkeypatch):
    gate = threading.Event()
    manager = make_manager(graph=FakeGraph(gate=gate), max_workers=1, max_pending=1)
    app.dependency_overrides[get_run_manager] = lambda: manager
    c = TestClient(app)
    try:
        assert c.post("/api/research", json={"question": QUESTION}).status_code == 202       # running
        assert c.post("/api/research", json={"question": QUESTION}).status_code == 202       # queued
        third = c.post("/api/research", json={"question": QUESTION})
        assert third.status_code == 429 and "try again" in third.json()["detail"]
    finally:
        gate.set()
        app.dependency_overrides.clear()
        manager.shutdown()


def test_unknown_ids_answer_404(client):
    for path in ("/api/research/nope", "/api/research/nope/events", "/api/research/nope/report"):
        r = client.get(path)
        assert r.status_code == 404 and r.json()["detail"] == "Research session not found"


def test_listing(client):
    run_id = client.post("/api/research", json={"question": QUESTION}).json()["id"]
    wait_finished(client.manager, run_id)
    items = client.get("/api/research?limit=5").json()["items"]
    assert [i["id"] for i in items] == [run_id] and set(items[0]) == {"id", "question", "status", "createdAt"}
    assert client.get("/api/research?limit=0").status_code == 422


# -------------------------------------------------------------------------------------------------------------------- events
def test_events_follow_the_stages_in_order(client):
    run_id = client.post("/api/research", json={"question": QUESTION}).json()["id"]
    wait_finished(client.manager, run_id)
    events = read_events(client, run_id)
    names = [(e["event"], e["stage"]) for e in events]
    assert names == [("run_queued", None), ("run_started", None), ("stage_started", "planner"), ("stage_completed", "planner"),
                     ("stage_started", "retrieval"), ("branch_completed", "retrieval"), ("branch_completed", "retrieval"),
                     ("stage_completed", "retrieval"), ("stage_started", "summarizer"), ("stage_completed", "summarizer"), ("run_completed", None)]
    assert [e["seq"] for e in events] == list(range(len(events)))
    planned = next(e for e in events if e["event"] == "stage_completed" and e["stage"] == "planner")
    assert planned["data"]["subQuestions"] == 2 and planned["data"]["queries"] == 4 and planned["data"]["domainAnchor"] == "deep learning"
    assert {e["data"]["branch"] for e in events if e["event"] == "branch_completed"} == {"papers", "web"}
    last = events[-1]
    assert last["data"]["reportUrl"] == f"/api/research/{run_id}/report" and last["data"]["stagesNotRun"] == ["factcheck", "report"]
    assert all(set(e) == {"seq", "event", "stage", "status", "message", "data", "timestamp"} for e in events)


def test_a_client_can_resume_after_a_reconnect(client):
    run_id = client.post("/api/research", json={"question": QUESTION}).json()["id"]
    wait_finished(client.manager, run_id)
    all_events = read_events(client, run_id)
    resumed = read_events(client, run_id, headers={"Last-Event-ID": "5"})
    assert [e["seq"] for e in resumed] == [e["seq"] for e in all_events][6:]
    assert [e["seq"] for e in read_events(client, run_id, query="?after=8")] == [9, 10]       # ?after= does the same for clients without headers


def test_a_failing_run_ends_with_run_failed(client):
    manager = make_manager(graph=FakeGraph(error=RuntimeError("model server is down")), max_workers=1)
    app.dependency_overrides[get_run_manager] = lambda: manager
    c = TestClient(app)
    run_id = c.post("/api/research", json={"question": QUESTION}).json()["id"]
    rec = wait_finished(manager, run_id)
    assert rec.status == "failed" and "model server is down" in rec.error
    session = c.get(f"/api/research/{run_id}").json()
    assert session["status"] == "failed" and session["stages"]["summarizer"] == "failed"
    events = read_events(c, run_id)
    assert events[-1]["event"] == "run_failed" and "RuntimeError" in events[-1]["message"] and events[-1]["stage"] == "summarizer"
    manager.shutdown()


def test_a_run_that_is_only_in_the_database_gets_one_closing_event(client, monkeypatch):
    monkeypatch.setattr(report_service, "session_from_db", lambda qid: {"id": qid, "status": "completed", "error": None, "question": "q"})
    events = read_events(client, "11111111-1111-1111-1111-111111111111")
    assert len(events) == 1 and events[0]["event"] == "run_completed"
    monkeypatch.setattr(report_service, "session_from_db", lambda qid: {"id": qid, "status": "failed", "error": "stopped", "question": "q"})
    assert read_events(client, "22222222-2222-2222-2222-222222222222")[0]["event"] == "run_failed"


def test_summaries_never_raise_on_a_surprising_update():
    for node in ("planner", "paper_retrieval", "web_search", "summarizer", "unknown"):
        message, data = rm.summarize_update(node, {"task_plan": 5, "paper_results": None, "web_sources": 7, "coverage": [1], "digests": None})
        assert isinstance(message, str) and isinstance(data, dict)


# --------------------------------------------------------------------------------------------------------------------- report
def test_a_report_is_refused_while_the_run_is_going(monkeypatch):
    gate = threading.Event()
    manager = make_manager(graph=FakeGraph(gate=gate), max_workers=1)
    app.dependency_overrides[get_run_manager] = lambda: manager
    monkeypatch.setattr(report_service, "build_report", lambda qid: {"id": qid})
    c = TestClient(app)
    try:
        run_id = c.post("/api/research", json={"question": QUESTION}).json()["id"]
        r = c.get(f"/api/research/{run_id}/report")
        assert r.status_code == 409 and "not finished" in r.json()["detail"]
        gate.set()
        wait_finished(manager, run_id)
        assert c.get(f"/api/research/{run_id}/report").json() == {"id": run_id}
    finally:
        gate.set()
        app.dependency_overrides.clear()
        manager.shutdown()


class FakeTable:
    def __init__(self, rows):
        self.rows, self._filters = rows, []

    def select(self, *_):
        return FakeTable(self.rows)

    def eq(self, col, val):
        t = FakeTable(self.rows); t._filters = self._filters + [(col, {val})]; return t

    def in_(self, col, vals):
        t = FakeTable(self.rows); t._filters = self._filters + [(col, set(vals))]; return t

    def order(self, *_, **__):
        return self

    def limit(self, *_):
        return self

    def execute(self):
        return SimpleNamespace(data=[r for r in self.rows if all(r.get(c) in v for c, v in self._filters)])


class FakeDb:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return FakeTable(self.tables.get(name, []))


QID = "aaaaaaaa-0000-0000-0000-000000000001"
T0 = "2026-11-05T15:40:00+00:00"


def db_fixture():
    sq = {"id": "sq1", "query_id": QID, "main_topic": "What is a MoE model?", "detail_questions": ["How does it differ from a dense model?"], "created_at": T0}
    cov = {"id": "c1", "query_id": QID, "sub_question_id": "sq1", "created_at": T0, "sufficient": False, "judge_used": True, "source_count": 2,
           "full_text_source_count": 1, "digest_failures": 0, "fallback_reason": None, "unjudged_aspects": [],
           "uncovered_aspects": ["What is a MoE model?"], "uncovered_reasons": {"What is a MoE model?": "judged_insufficient"},
           "judge_stats": {"aspect_merge": "exact", "topic_aspect": True},
           "aspect_evidence": {"0": [{"verdict": "yes", "source_id": "p1"}, {"verdict": "yes", "source_id": "w1"}, {"verdict": "no", "source_id": "w1"}],
                               "1": [{"verdict": "yes", "source_id": "p1"}]}}
    finding = {"claim": "MoE routes tokens to a few experts.", "quote": "a gating function routes each input to a few experts", "stance": "supports",
               "verified": True, "judge": {"0": {"aspect": "How does it differ from a dense model?", "final": "yes", "quote_supports_claim": "yes",
                                                 "answers_aspect": "yes", "reason": "Direct."}}}
    digests = [{"id": "d1", "query_id": QID, "sub_question_id": "sq1", "source_type": "paper", "source_id": "p1", "source_title": "A Survey on MoE",
                "evidence_level": "full_text", "weight": 0.9, "total_count": 2, "verified_count": 1, "created_at": T0,
                "findings": json.dumps([finding, {"claim": "c2", "quote": "q2", "stance": "neutral", "verified": False}])},
               {"id": "d2", "query_id": QID, "sub_question_id": "sq1", "source_type": "web", "source_id": "w1", "source_title": "What is MoE? / IBM",
                "evidence_level": "web_snippet", "weight": 0.5, "total_count": 0, "verified_count": 0, "created_at": T0, "findings": []}]
    return {"research_queries": [{"id": QID, "raw_query": "What is mixture of experts?", "created_at": T0}], "sub_questions": [sq],
            "coverage_results": [cov], "digests": digests,
            "retrieved_papers": [{"id": "p1", "doi": "10.1/x", "arxiv_id": None, "pdf_url": None, "authors": ["A. Author"], "year": 2024, "venue": "arXiv",
                                  "citation_count": 12, "source": "openalex"}],
            "web_sources": [{"id": "w1", "url": "https://www.ibm.com/think/topics/mixture-of-experts", "provider": "tavily", "published_date": None}]}


def test_the_report_is_built_from_the_database(monkeypatch):
    from apps.api.agents.stage3_summarizer import detail_aspects as da
    monkeypatch.setattr(report_service, "supabase", FakeDb(db_fixture()))
    da._save_cache_entry(da._cache_key("sq1", "How does it differ from a dense model?"), ["How does it differ from a dense model?"])
    report = report_service.build_report(QID)
    assert report["question"] == "What is mixture of experts?" and report["stages"]["factcheck"] == "not_run" and report["stages"]["report"] == "not_run"
    assert report["totals"] == {"subQuestions": 1, "subQuestionsSufficient": 0, "sources": 2, "findings": 2, "findingsQuoteFound": 1,
                                "factChecked": None}
    assert report["subQuestions"][0]["factCheck"] is None and any("Stage 4" in x and "did not run" in x for x in report["limitations"])
    sq = report["subQuestions"][0]
    cov = sq["coverage"]
    assert cov["sufficient"] is False and cov["uncoveredAspects"] == ["What is a MoE model?"]
    assert [(a["text"], a["state"], a["yesVerdicts"], a["sources"]) for a in cov["aspects"]] == [
        ("How does it differ from a dense model?", "covered", 2, 2), ("What is a MoE model?", "judged_insufficient", 1, 1)]
    paper, web = sq["sources"]                           # ordered by weight
    assert paper["url"] == "https://doi.org/10.1/x" and paper["year"] == 2024 and paper["findings"][0]["quoteFound"] is True
    assert paper["findings"][0]["judgements"][0]["verdict"] == "yes" and paper["findings"][1]["quoteFound"] is False
    assert web["url"].startswith("https://www.ibm.com") and web["evidenceLevel"] == "web_snippet"
    assert any("Evidence is not sufficient for: What is a MoE model?" in x for x in report["limitations"]) and any("Stage 5" in x for x in report["limitations"])


def test_the_report_works_without_the_aspect_cache(monkeypatch):
    monkeypatch.setattr(report_service, "supabase", FakeDb(db_fixture()))
    cov = report_service.build_report(QID)["subQuestions"][0]["coverage"]
    assert [a["text"] for a in cov["aspects"]] == [None, None] and cov["uncoveredAspects"] == ["What is a MoE model?"]


def test_a_sub_question_without_stage_3_rows_is_reported_as_unfinished(monkeypatch):
    tables = db_fixture()
    tables["coverage_results"], tables["digests"] = [], []
    monkeypatch.setattr(report_service, "supabase", FakeDb(tables))
    report = report_service.build_report(QID)
    assert report["stages"]["summarizer"] == "incomplete" and report["subQuestions"][0]["coverage"] is None
    assert any("Stage 3 did not finish" in x for x in report["limitations"])


def test_session_from_db(monkeypatch):
    monkeypatch.setattr(report_service, "supabase", FakeDb(db_fixture()))
    assert report_service.session_from_db(QID)["status"] == "completed"
    assert report_service.session_from_db("missing") is None
    tables = db_fixture(); tables["coverage_results"] = []
    monkeypatch.setattr(report_service, "supabase", FakeDb(tables))
    session = report_service.session_from_db(QID)
    assert session["status"] == "failed" and "did not finish" in session["error"]


# ----------------------------------------------------------------------------------------------------------------- the rest
def test_health_and_cors(client):
    assert client.get("/health").json() == {"status": "ok", "activeRuns": 0}
    ok = client.options("/api/research", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"})
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == "http://localhost:3000"
    bad = client.options("/api/research", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in bad.headers


def test_the_report_shows_the_stage_4_result_when_it_ran(monkeypatch):
    tables = db_fixture()
    tables["fact_claims"] = [
        {"id": "f1", "query_id": QID, "sub_question_id": "sq1", "claim": "MoE activates few experts per token.", "label": "supported", "confidence": 0.8,
         "support_doc_count": 2, "contra_doc_count": 0, "contested": False,
         "evidence": [{"source_id": "p1", "source_title": "A Survey on MoE", "quote": "routes each input to a few experts", "relation": "supports",
                       "reliability": 0.8, "evidence_level": "full_text", "prob": 0.97}]},
        {"id": "f2", "query_id": QID, "sub_question_id": "sq1", "claim": "MoE is cheaper to train.", "label": "unverified", "confidence": 0.5,
         "support_doc_count": 1, "contra_doc_count": 0, "contested": False, "evidence": []},
        {"id": "f3", "query_id": QID, "sub_question_id": "sq1", "claim": "Routing is stable.", "label": "contradicted", "confidence": 0.7,
         "support_doc_count": 1, "contra_doc_count": 1, "contested": False, "evidence": json.dumps([{"source_id": "w1", "quote": "unstable", "relation": "contradicts"}])}]
    tables["contradictions"] = [{"id": "x1", "query_id": QID, "sub_question_id": "sq1", "claim_a": "Routing is stable.", "claim_b": "Routing is unstable.",
                                 "source_a_title": "A", "source_b_title": "B", "quote_a": "qa", "quote_b": "qb", "prob": 0.9, "reason": "Opposite assertions."}]
    monkeypatch.setattr(report_service, "supabase", FakeDb(tables))
    report = report_service.build_report(QID)
    fc = report["subQuestions"][0]["factCheck"]
    assert report["stages"]["factcheck"] == "completed" and report["totals"]["factChecked"] == {"contradicted": 1, "supported": 1, "partially_supported": 0, "unverified": 1, "contested": 0}
    assert [c["label"] for c in fc["claims"]] == ["contradicted", "supported", "unverified"]           # contradicted first
    assert fc["claims"][1]["evidence"][0]["sourceTitle"] == "A Survey on MoE" and fc["claims"][2]["evidence"] == []
    assert fc["claims"][0]["evidence"][0]["quote"] == "unstable"                                       # jsonb arrives as text in some clients
    assert fc["disagreements"][0]["reason"] == "Opposite assertions." and fc["counts"]["contradicted"] == 1
    assert report["limitations"][0].startswith("Stage 4 compared") and any("Sources disagree" in x for x in report["limitations"])
