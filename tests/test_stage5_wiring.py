"""Stage 5 wiring (offline: fakes only): the graph node after factcheck, the run's `report` stage and its events, the derived `stages.report` of a stored
run, the written-report endpoints, and the database functions (including the table that does not exist yet). The node itself (report_node.py) and the
assembler are NOT used here: they are replaced by fakes."""
import sys
import threading
import time
import types
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.api.dependencies import get_run_manager  # noqa: E402
from apps.api.main import app  # noqa: E402
from apps.api.services import db_errors, db_service, progress, report_service, run_manager as rm  # noqa: E402

QUESTION = "How do state space models compare with transformers in training efficiency?"
QID = "bbbbbbbb-0000-0000-0000-000000000002"
OK_UPDATE = {"written_report": {"sections": [{"sentences": [{"text": "a"}, {"text": "b"}]}, {"sentences": [{"text": "c"}]}],
                                "references": [{"number": 1}], "warnings": ["w"]},
             "written_report_status": "completed_with_warnings"}


# ----------------------------------------------------------------------------------------------------------------------- the graph
def test_the_graph_runs_the_report_node_after_factcheck(monkeypatch):
    order = []

    def node(name, update):
        def fn(state):
            order.append(name)
            return update
        return fn
    fakes = {"planner_node": ("planner_node", {}), "paper_retrieval_node": ("paper_retrieval_node", {"paper_results": [{}]}),
             "web_search_node": ("web_search_node", {"web_sources": []}), "summarizer_node": ("summarizer_node", {"digests": [{}]}),
             "factcheck_node": ("factcheck_node", {}), "report_node": ("report_node", OK_UPDATE)}
    for module, (fn_name, update) in fakes.items():
        mod = types.ModuleType(f"apps.api.graph.nodes.{module}")
        setattr(mod, fn_name, node(module, update))
        monkeypatch.setitem(sys.modules, f"apps.api.graph.nodes.{module}", mod)
    monkeypatch.delitem(sys.modules, "apps.api.graph.build_graph", raising=False)
    from apps.api.graph.build_graph import build_graph
    from apps.api.graph.state import SharedResearchState

    graph = build_graph()
    chunks = [list(c) for c in graph.stream(SharedResearchState(raw_query=QUESTION), stream_mode="updates")]
    names = [n for c in chunks for n in c]
    assert names[-2:] == ["factcheck", "report"] and names.index("summarizer") < names.index("factcheck")
    final = graph.invoke(SharedResearchState(raw_query=QUESTION))
    assert final["written_report_status"] == "completed_with_warnings" and final["written_report"]["references"] == [{"number": 1}]   # the fields survive in the state
    assert SharedResearchState(raw_query="q").written_report == {} and SharedResearchState(raw_query="q").written_report_status == ""


# ------------------------------------------------------------------------------------------------------------------- run manager
class GraphWithReport:
    """The real order of the updates: planner, both retrieval branches, summarizer, factcheck, report. `report` is the update of the report node
    (None = {}), or an exception to raise in its place."""
    def __init__(self, report=None, fact=None, steps=False):
        self.report, self.fact, self.steps = report, fact if fact is not None else {}, steps

    def stream(self, state, stream_mode):
        sq = SimpleNamespace(main_topic="What are SSMs?", queries=["a"])
        yield {"planner": {"task_plan": SimpleNamespace(sub_questions=[sq], domain_anchor="")}}
        yield {"paper_retrieval": {"paper_results": []}}
        yield {"web_search": {"web_sources": []}}
        yield {"summarizer": {"digests": [1], "coverage": {"a": {"sufficient": True}}}}
        yield {"factcheck": self.fact or None}
        if self.steps:                                           # what the report node does while it runs
            progress.report(state.query_id, "report", "write", "running", "Writing section 1 of 2", section=1, sections=2)
            progress.note(state.query_id, "stage5_skipped", "Skipped a section", level="warn", stage="report", sections=1)
        if isinstance(self.report, Exception):
            raise self.report
        yield {"report": self.report}


def run_to_end(graph, monkeypatch, stage5):
    monkeypatch.setenv("STAGE5", "true" if stage5 else "false")
    manager = rm.RunManager(graph_factory=lambda: graph, max_workers=1)
    try:
        rec = manager.submit(QUESTION)
        for _ in range(250):
            if rec.finished:
                break
            time.sleep(0.02)
        assert rec.finished
        return rec
    finally:
        manager.shutdown()


def report_events(rec):
    return [e for e in rec.events if e["stage"] == "report"]


def test_the_report_stage_runs_and_reports_its_result_when_stage5_is_on(monkeypatch):
    rec = run_to_end(GraphWithReport(OK_UPDATE, steps=True), monkeypatch, True)
    assert rec.status == "completed" and rec.stages["report"] == "completed" and rec.stages["factcheck"] == "not_run"
    ev = report_events(rec)
    assert [e["event"] for e in ev if e["event"].startswith("stage_")] == ["stage_started", "stage_completed"]
    done = [e for e in ev if e["event"] == "stage_completed"][0]
    assert done["status"] == "completed" and "completed_with_warnings" in done["message"]
    assert {k: v for k, v in done["data"].items() if k != "groq"} == {"status": "completed_with_warnings", "sections": 2, "sentences": 3, "references": 1, "warnings": 1}
    steps = [e for e in ev if e["event"] == "step"]                                  # the progress lane "report" and its notes belong to the report stage
    assert [(e["data"]["lane"], e["data"]["step"]) for e in steps] == [("report", "write"), ("notes", "stage5_skipped")]
    assert rec.events[-1]["event"] == "run_completed" and "report" not in rec.events[-1]["data"]["stagesNotRun"]
    assert rec.events.index(done) > rec.events.index([e for e in ev if e["event"] == "stage_started"][0])


def test_the_report_stage_is_not_run_when_stage5_is_off(monkeypatch):
    rec = run_to_end(GraphWithReport(None), monkeypatch, False)
    assert rec.status == "completed" and rec.stages["report"] == "not_run" and not report_events(rec)
    assert rec.events[-1]["data"]["stagesNotRun"] == ["factcheck", "report"]


def test_the_report_stage_is_pending_at_the_start_when_stage5_is_on(monkeypatch):
    monkeypatch.setenv("STAGE5", "true")
    assert rm.RunRecord("x", "q").stages["report"] == "pending"
    monkeypatch.setenv("STAGE5", "false")
    assert rm.RunRecord("x", "q").stages["report"] == "not_run"


def test_a_report_node_that_does_nothing_leaves_the_stage_not_run(monkeypatch):
    rec = run_to_end(GraphWithReport({}), monkeypatch, True)                           # e.g. the node skipped itself
    assert rec.status == "completed" and rec.stages["report"] == "not_run"
    assert [(e["event"], e["status"]) for e in report_events(rec)] == [("stage_started", "running"), ("stage_completed", "not_run")]
    assert "report" in rec.events[-1]["data"]["stagesNotRun"]


def test_a_failed_written_report_fails_the_stage_but_not_the_run(monkeypatch):
    rec = run_to_end(GraphWithReport({"written_report": {"warnings": ["x"]}, "written_report_status": "failed"}), monkeypatch, True)
    assert rec.status == "completed" and rec.error is None and rec.stages["report"] == "failed"
    assert report_events(rec)[-1]["status"] == "failed" and "evidence report is still available" in report_events(rec)[-1]["message"]
    assert rec.events[-1]["event"] == "run_completed"


def test_a_report_node_that_raises_never_fails_the_run(monkeypatch):
    rec = run_to_end(GraphWithReport(RuntimeError("boom"), fact={"fact_claims": [], "fact_summary": {"a": {}}}), monkeypatch, True)
    assert rec.status == "completed" and rec.error is None and rec.stages["report"] == "failed"
    last = report_events(rec)[-1]
    assert last["event"] == "stage_completed" and last["status"] == "failed" and "RuntimeError" in last["message"]
    assert [e["event"] for e in rec.events][-1] == "run_completed" and not [e for e in rec.events if e["event"] == "run_failed"]


def test_an_error_before_the_report_stage_still_fails_the_run(monkeypatch):
    class Early(GraphWithReport):
        def stream(self, state, stream_mode):
            yield {"planner": {"task_plan": SimpleNamespace(sub_questions=[], domain_anchor="")}}
            raise RuntimeError("retrieval broke")
    rec = run_to_end(Early(), monkeypatch, True)
    assert rec.status == "failed" and rec.stages["report"] == "pending" and rec.events[-1]["event"] == "run_failed"


def test_summarize_update_for_the_report_node():
    msg, data = rm.summarize_update("report", {})
    assert msg and data == {}
    msg, data = rm.summarize_update("report", OK_UPDATE)
    assert data["status"] == "completed_with_warnings" and data["sentences"] == 3 and "2 sections" in msg
    assert rm.summarize_update("report", {"written_report_status": "completed", "written_report": 5}) == ("", {})   # a surprise shape gives an empty summary
    assert "report" in rm.NODE_STAGE and rm.LANE_STAGE["report"] == "report" and "report" not in rm.NOT_BUILT and "report" in progress.LANES


# ---------------------------------------------------------------------------------------------------------------- report_service
class FakeTable:
    def __init__(self, rows, error=None):
        self.rows, self.error, self.filters = rows, error, []

    def select(self, *_):
        return self

    def eq(self, col, val):
        self.filters.append((col, val))
        return self

    def in_(self, col, vals):
        self.filters.append((col, set(vals)))
        return self

    def limit(self, *_):
        return self

    def execute(self):
        if self.error:
            raise self.error
        return SimpleNamespace(data=[r for r in self.rows if all(r.get(c) in v if isinstance(v, set) else r.get(c) == v for c, v in self.filters)])


class FakeDb:
    def __init__(self, tables=None, error=None):
        self.tables, self.error = tables or {}, error

    def table(self, name):
        return FakeTable(self.tables.get(name, []), self.error if name == "written_reports" else None)


@pytest.mark.parametrize("status,expected", [("completed", "completed"), ("completed_with_warnings", "completed"),
                                             ("insufficient_evidence", "completed"), ("failed", "failed")])
def test_the_report_stage_of_a_stored_run_comes_from_the_stored_status(monkeypatch, status, expected):
    monkeypatch.setattr(report_service, "supabase", FakeDb({"written_reports": [{"query_id": QID, "status": status}]}))
    assert report_service.written_report_stage(QID) == expected


def test_no_row_or_no_table_means_not_run(monkeypatch):
    monkeypatch.setattr(report_service, "supabase", FakeDb({"written_reports": [{"query_id": "other", "status": "completed"}]}))
    assert report_service.written_report_stage(QID) == "not_run"
    monkeypatch.setattr(report_service, "supabase", FakeDb(error=Exception("Could not find the table 'public.written_reports' in the schema cache")))
    assert report_service.written_report_stage(QID) == "not_run"
    monkeypatch.setattr(report_service, "supabase", FakeDb(error=httpx.ConnectError("down")))
    with pytest.raises(httpx.ConnectError):                                              # a connection error is not "not_run": the route answers 503
        report_service.written_report_stage(QID)


def stored_run_tables(written=None):
    t0 = "2026-11-05T15:40:00+00:00"
    sq = {"id": "sq1", "query_id": QID, "main_topic": "What is a MoE model?", "detail_questions": [], "created_at": t0}
    cov = {"id": "c1", "query_id": QID, "sub_question_id": "sq1", "created_at": t0, "sufficient": True, "judge_stats": {}, "aspect_evidence": {}}
    return {"research_queries": [{"id": QID, "raw_query": "What is MoE?", "created_at": t0}], "sub_questions": [sq], "coverage_results": [cov],
            "written_reports": written or []}


def test_the_stored_run_reports_the_derived_report_stage(monkeypatch):
    monkeypatch.setattr(report_service, "supabase", FakeDb(stored_run_tables()))
    assert report_service.session_from_db(QID)["stages"]["report"] == "not_run"
    rep = report_service.build_report(QID)
    assert rep["stages"]["report"] == "not_run" and any("Stage 5" in x and "did not run" in x for x in rep["limitations"])
    assert not any("not built" in x for x in rep["limitations"])
    monkeypatch.setattr(report_service, "supabase", FakeDb(stored_run_tables([{"query_id": QID, "status": "completed_with_warnings"}])))
    assert report_service.session_from_db(QID)["stages"]["report"] == "completed"
    rep = report_service.build_report(QID)
    assert rep["stages"]["report"] == "completed" and not any("Stage 5" in x for x in rep["limitations"])
    monkeypatch.setattr(report_service, "supabase", FakeDb(stored_run_tables([{"query_id": QID, "status": "failed"}])))
    assert report_service.session_from_db(QID)["stages"]["report"] == "failed" and report_service.build_report(QID)["stages"]["report"] == "failed"


# ---------------------------------------------------------------------------------------------------------------------- endpoints
@pytest.fixture
def client(monkeypatch):
    manager = rm.RunManager(graph_factory=lambda: GraphWithReport(), max_workers=1, max_pending=3)
    app.dependency_overrides[get_run_manager] = lambda: manager
    monkeypatch.setattr(db_errors, "RETRY_DELAY_SECONDS", 0)
    monkeypatch.setattr(report_service, "session_from_db", lambda qid: {"id": qid})
    with report_service._running_lock:
        report_service._running.clear()
        report_service._failed.clear()
    c = TestClient(app)
    c.manager = manager
    yield c
    app.dependency_overrides.clear()
    manager.shutdown()
    with report_service._running_lock:
        report_service._running.clear()
        report_service._failed.clear()


ROW = {"query_id": QID, "status": "completed", "report": {"status": "completed", "sections": []}, "markdown": "# Report", "stats": {"sentences": 3},
       "model": "openai/gpt-oss-120b", "template_version": "s5-v1", "created_at": "2026-11-11T10:00:00+00:00", "updated_at": "2026-11-11T10:05:00+00:00"}


def test_get_written_report_404_when_there_is_none(client, monkeypatch):
    monkeypatch.setattr(db_service, "get_written_report", lambda qid: None)
    r = client.get(f"/api/research/{QID}/written-report")
    assert r.status_code == 404 and "No written report" in r.json()["detail"]
    assert client.get("/api/research/not-a-uuid/written-report").status_code == 404


def test_get_written_report_200_with_the_stored_report(client, monkeypatch):
    monkeypatch.setattr(db_service, "get_written_report", lambda qid: ROW)
    r = client.get(f"/api/research/{QID}/written-report")
    assert r.status_code == 200
    assert r.json() == {"status": "completed", "report": {"status": "completed", "sections": []}, "markdown": "# Report", "stats": {"sentences": 3},
                        "model": "openai/gpt-oss-120b", "templateVersion": "s5-v1", "generatedAt": "2026-11-11T10:05:00+00:00"}


def test_get_written_report_says_running_while_it_is_being_written(client, monkeypatch):
    monkeypatch.setattr(db_service, "get_written_report", lambda qid: ROW)             # an older report exists: the new one is on its way
    with report_service._running_lock:
        report_service._running.add(QID)
    r = client.get(f"/api/research/{QID}/written-report")
    assert r.status_code == 202 and r.json() == {"state": "running"}


def test_get_written_report_is_503_when_the_database_is_down(client, monkeypatch):
    def down(qid):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(db_service, "get_written_report", down)
    assert client.get(f"/api/research/{QID}/written-report").status_code == 503


def test_post_written_report_is_400_when_stage5_is_off(client):
    r = client.post(f"/api/research/{QID}/written-report")
    assert r.status_code == 400 and "STAGE5" in r.json()["detail"]


def test_post_written_report_is_409_when_one_is_already_running(client, monkeypatch):
    monkeypatch.setenv("STAGE5", "true")
    with report_service._running_lock:
        report_service._running.add(QID)
    r = client.post(f"/api/research/{QID}/written-report")
    assert r.status_code == 409 and "already" in r.json()["detail"]


def test_post_written_report_is_404_for_an_unknown_run_and_409_for_a_live_one(client, monkeypatch):
    monkeypatch.setenv("STAGE5", "true")
    monkeypatch.setattr(report_service, "session_from_db", lambda qid: None)
    assert client.post(f"/api/research/{QID}/written-report").status_code == 404
    assert client.post("/api/research/not-a-uuid/written-report").status_code == 404
    gate = threading.Event()

    class Slow(GraphWithReport):
        def stream(self, state, stream_mode):
            gate.wait(5)
            return super().stream(state, stream_mode)
    manager = rm.RunManager(graph_factory=lambda: Slow(), max_workers=1)
    app.dependency_overrides[get_run_manager] = lambda: manager
    try:
        run_id = TestClient(app).post("/api/research", json={"question": QUESTION}).json()["id"]
        assert TestClient(app).post(f"/api/research/{run_id}/written-report").status_code == 409
    finally:
        gate.set()
        manager.shutdown()


def fake_stage5_modules(monkeypatch, build):
    loader = types.ModuleType("apps.api.agents.stage5_report.loader")
    loader.load_inputs = lambda qid, **kw: {"query_id": qid}
    assembler = types.ModuleType("apps.api.agents.stage5_report.assembler")
    assembler.build_report = build
    import apps.api.agents.stage5_report as package             # `from package import loader` finds the attribute first, so patch both
    monkeypatch.setitem(sys.modules, "apps.api.agents.stage5_report.loader", loader)
    monkeypatch.setitem(sys.modules, "apps.api.agents.stage5_report.assembler", assembler)
    monkeypatch.setattr(package, "loader", loader, raising=False)
    monkeypatch.setattr(package, "assembler", assembler, raising=False)


def wait_idle(qid):
    for _ in range(250):
        if not report_service.written_report_running(qid):
            return
        time.sleep(0.02)
    raise AssertionError("the background thread did not finish")


def test_post_written_report_runs_stage5_on_the_stored_run_in_the_background(client, monkeypatch):
    monkeypatch.setenv("STAGE5", "true")
    gate, writes = threading.Event(), []

    def build(inputs, **kw):
        assert inputs == {"query_id": QID}
        gate.wait(5)
        return {"status": "completed", "report": {"sections": []}, "markdown": "# R", "stats": {"n": 1}, "warnings": [], "model": "m", "template_version": "s5-v1"}
    fake_stage5_modules(monkeypatch, build)
    monkeypatch.setattr(db_service, "write_written_report", lambda *a: writes.append(a) or True)
    r = client.post(f"/api/research/{QID}/written-report")
    assert r.status_code == 202 and r.json() == {"state": "started"}
    assert client.post(f"/api/research/{QID}/written-report").status_code == 409            # the first one is still writing
    gate.set()
    wait_idle(QID)
    assert writes == [(QID, "completed", {"sections": []}, "# R", {"n": 1}, "m", "s5-v1")]


def test_a_background_run_that_cannot_store_its_report_says_why(client, monkeypatch):
    monkeypatch.setenv("STAGE5", "true")
    fake_stage5_modules(monkeypatch, lambda inputs, **kw: {"status": "completed", "report": {}, "markdown": "", "stats": {}, "model": "m", "template_version": "v"})
    monkeypatch.setattr(db_service, "write_written_report", lambda *a: False)               # the table does not exist yet
    monkeypatch.setattr(db_service, "get_written_report", lambda qid: None)
    assert client.post(f"/api/research/{QID}/written-report").status_code == 202
    wait_idle(QID)
    r = client.get(f"/api/research/{QID}/written-report")
    assert r.status_code == 404 and "016" in r.json()["detail"]
    assert client.post(f"/api/research/{QID}/written-report").status_code == 202            # a new attempt is allowed after a failure
    wait_idle(QID)


# ---------------------------------------------------------------------------------------------------------------------- db_service
class FakeClient:
    """supabase.table(name).upsert(...)/select(...).eq(...).limit(...).execute() with a recorded call list and an optional error."""
    def __init__(self, rows=None, error=None):
        self.rows, self.error, self.calls = rows or [], error, []

    def table(self, name):
        self.calls.append(("table", name))
        return self

    def upsert(self, row, on_conflict=None):
        self.calls.append(("upsert", row, on_conflict))
        return self

    def select(self, cols):
        self.calls.append(("select", cols))
        return self

    def eq(self, col, val):
        self.calls.append(("eq", col, val))
        return self

    def limit(self, n):
        return self

    def execute(self):
        if self.error:
            raise self.error
        return SimpleNamespace(data=self.rows)


MISSING = Exception("{'code': 'PGRST205', 'message': \"Could not find the table 'public.written_reports' in the schema cache\"}")


def test_write_written_report_upserts_on_query_id(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(db_service, "supabase", fake)
    assert db_service.write_written_report(QID, "completed", {"a": "x\x00y"}, "md\x00", {"n": 1}, "model", "s5-v1") is True
    _, row, on_conflict = [c for c in fake.calls if c[0] == "upsert"][0]
    assert ("table", "written_reports") in fake.calls and on_conflict == "query_id"
    assert row["query_id"] == QID and row["status"] == "completed" and row["report"] == {"a": "xy"} and row["markdown"] == "md"
    assert row["stats"] == {"n": 1} and row["model"] == "model" and row["template_version"] == "s5-v1" and row["updated_at"] and "created_at" not in row


def test_write_written_report_tolerates_a_missing_table(monkeypatch, caplog):
    monkeypatch.setattr(db_service, "supabase", FakeClient(error=MISSING))
    with caplog.at_level("WARNING", logger="apps.api.services.db"):
        assert db_service.write_written_report(QID, "completed", {}, "", {}, "m", "v") is False
    assert "016" in caplog.text
    monkeypatch.setattr(db_service, "supabase", FakeClient(error=Exception('relation "written_reports" does not exist')))
    assert db_service.write_written_report(QID, "completed", {}, "", {}, "m", "v") is False


def test_write_written_report_raises_other_errors(monkeypatch):
    monkeypatch.setattr(db_service, "supabase", FakeClient(error=RuntimeError("permission denied for table written_reports")))
    with pytest.raises(RuntimeError):
        db_service.write_written_report(QID, "completed", {}, "", {}, "m", "v")


def test_get_written_report_reads_the_row_or_none(monkeypatch, caplog):
    fake = FakeClient(rows=[ROW])
    monkeypatch.setattr(db_service, "supabase", fake)
    assert db_service.get_written_report(QID) == ROW and ("eq", "query_id", QID) in fake.calls
    monkeypatch.setattr(db_service, "supabase", FakeClient(rows=[]))
    assert db_service.get_written_report(QID) is None
    monkeypatch.setattr(db_service, "supabase", FakeClient(error=MISSING))
    with caplog.at_level("WARNING", logger="apps.api.services.db"):
        assert db_service.get_written_report(QID) is None
    assert "016" in caplog.text
    monkeypatch.setattr(db_service, "supabase", FakeClient(error=RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        db_service.get_written_report(QID)
