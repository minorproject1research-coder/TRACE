"""Database failures and malformed ids in the API: a hiccup is retried once, a lasting failure is a 503 (never a 404), a non-uuid id is a 404
without touching the database. Found in the production readiness audit (docs/PRODUCTION_READINESS.md). Offline."""
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.api.dependencies import get_run_manager  # noqa: E402
from apps.api.main import app  # noqa: E402
from apps.api.services import db_errors, paper_service, report_service, run_manager as rm  # noqa: E402

GOOD = "cc81e9cc-1bfd-48d1-a3cc-ed23e8c00320"


@pytest.fixture
def client(monkeypatch):
    manager = rm.RunManager(graph_factory=lambda: None, max_workers=1)
    app.dependency_overrides[get_run_manager] = lambda: manager
    monkeypatch.setattr(db_errors, "RETRY_DELAY_SECONDS", 0)
    yield TestClient(app)
    app.dependency_overrides.clear()
    manager.shutdown()


def failing(times, result):
    """A function that raises the error seen in production `times` times, then returns result."""
    calls = {"n": 0}

    def fn(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] <= times:
            raise httpx.RemoteProtocolError("Server disconnected without sending a response.")
        return result
    fn.calls = calls
    return fn


def nothing_may_touch_the_database(*args, **kwargs):
    raise AssertionError("the database must not be asked about an id that cannot exist")


def test_a_dropped_connection_is_retried_once(client, monkeypatch):
    fn = failing(1, {"id": GOOD, "question": "q", "status": "completed", "error": None})
    monkeypatch.setattr(report_service, "session_from_db", fn)
    r = client.get(f"/api/research/{GOOD}")
    assert r.status_code == 200 and r.json()["status"] == "completed" and fn.calls["n"] == 2


def test_a_lasting_failure_is_503_not_404_or_500(client, monkeypatch):
    for target, path in ((report_service, f"/api/research/{GOOD}/report"), (report_service, f"/api/research/{GOOD}"),
                         (report_service, "/api/research"), (paper_service, f"/api/research/{GOOD}/papers")):
        name = {f"/api/research/{GOOD}/report": "build_report", f"/api/research/{GOOD}": "session_from_db",
                "/api/research": "list_sessions", f"/api/research/{GOOD}/papers": "build_papers_overview"}[path]
        monkeypatch.setattr(target, name, failing(99, None))
        r = client.get(path)
        assert r.status_code == 503, path
        assert r.headers["retry-after"] == "2" and "temporarily unavailable" in r.json()["detail"], path


def test_the_paper_page_and_the_events_route_also_answer_503(client, monkeypatch):
    monkeypatch.setattr(paper_service, "build_paper_detail", failing(99, None))
    assert client.get(f"/api/research/{GOOD}/papers/{GOOD}").status_code == 503
    monkeypatch.setattr(report_service, "session_from_db", failing(99, None))
    assert client.get(f"/api/research/{GOOD}/events").status_code == 503


def test_an_existing_report_is_not_called_missing_after_a_hiccup(client, monkeypatch):
    fn = failing(1, {"id": GOOD, "question": "q", "subQuestions": []})
    monkeypatch.setattr(report_service, "build_report", fn)
    assert client.get(f"/api/research/{GOOD}/report").json()["id"] == GOOD


def test_an_id_that_is_not_a_uuid_is_404_without_a_database_call(client, monkeypatch):
    for name in ("session_from_db", "build_report"):
        monkeypatch.setattr(report_service, name, nothing_may_touch_the_database)
    for name in ("build_papers_overview", "build_paper_detail"):
        monkeypatch.setattr(paper_service, name, nothing_may_touch_the_database)
    for path in ("/api/research/not-a-uuid", "/api/research/not-a-uuid/report", "/api/research/not-a-uuid/events",
                 "/api/research/not-a-uuid/papers", "/api/research/not-a-uuid/papers/also-not", "/api/research/1;drop/report"):
        assert client.get(path).status_code == 404, path


def test_other_errors_are_not_swallowed(client, monkeypatch):
    """Only connection errors are retried and mapped to 503; a bug must stay visible (500) and must not turn into a polite 404."""
    monkeypatch.setattr(report_service, "build_report", lambda qid: (_ for _ in ()).throw(KeyError("boom")))
    with pytest.raises(KeyError):
        TestClient(app, raise_server_exceptions=True).get(f"/api/research/{GOOD}/report")


def test_valid_uuid():
    assert db_errors.valid_uuid(GOOD) and not db_errors.valid_uuid("nope") and not db_errors.valid_uuid("")
