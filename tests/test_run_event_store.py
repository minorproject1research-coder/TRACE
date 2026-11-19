"""The timeline of a run is kept in the table run_events (migration 017) and replayed after a restart of the server. Offline: the database is a
small in-memory fake, the graph is a fake."""
import json
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.api import config  # noqa: E402
from apps.api.dependencies import get_run_manager  # noqa: E402
from apps.api.main import app  # noqa: E402
from apps.api.services import report_service, run_event_store as store, run_manager as rm  # noqa: E402

# the conftest replaces these two for every test (no test may read the real table); the store's own tests need the real ones
REAL_GET_EVENTS, REAL_GET_RUN_TIMES = store.get_events, store.get_run_times

RUN = "11111111-1111-1111-1111-111111111111"
T = "2026-11-17T04:20:{:02d}+00:00"


class MemTable:
    def __init__(self, db):
        self.db, self._filters, self._order, self._range, self._upsert, self._columns = db, [], None, None, None, None

    def upsert(self, rows, on_conflict=None):
        self._upsert = (rows, on_conflict)
        return self

    def select(self, columns):
        self._columns = [c.strip() for c in columns.split(",")] if columns != "*" else None
        return self

    def eq(self, column, value):
        self._filters.append((column, {value}))
        return self

    def in_(self, column, values):
        self._filters.append((column, set(values)))
        return self

    def order(self, column):
        self._order = column
        return self

    def range(self, a, b):
        self._range = (a, b)
        return self

    def execute(self):
        self.db.calls += 1
        if self.db.errors:
            raise self.db.errors.pop(0)
        if self._upsert:
            rows, conflict = self._upsert
            assert conflict == "query_id,seq"
            for r in rows:
                self.db.rows[(r["query_id"], r["seq"])] = dict(r)
            self.db.batches.append(len(rows))
            return SimpleNamespace(data=rows)
        rows = [r for r in self.db.rows.values() if all(r.get(c) in v for c, v in self._filters)]
        if self._order:
            rows.sort(key=lambda r: r[self._order])
        if self._range:
            rows = rows[self._range[0]:self._range[1] + 1]
        if self._columns:
            rows = [{c: r.get(c) for c in self._columns} for r in rows]
        return SimpleNamespace(data=rows)


class MemDb:
    def __init__(self):
        self.rows, self.errors, self.calls, self.batches = {}, [], 0, []

    def table(self, name):
        assert name == "run_events"
        return MemTable(self)


def ev(seq, event, stage=None, status=None, message="", data=None):
    return {"seq": seq, "event": event, "stage": stage, "status": status, "message": message, "data": data or {}, "timestamp": T.format(seq)}


def a_finished_run():
    return [ev(0, "run_queued", status="pending", message="Queued"), ev(1, "run_started", status="running"),
            ev(2, "stage_started", "planner", "running"), ev(3, "stage_completed", "planner", "completed", "Planned 2 sub-questions", {"subQuestions": 2}),
            ev(4, "step", "retrieval", "running", "Searching", {"lane": "papers", "step": "search", "state": "running", "occurredAt": T.format(4)}),
            ev(5, "run_completed", status="completed", message="Run finished", data={"reportUrl": f"/api/research/{RUN}/report"})]


def wait_for(condition, seconds=3.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return condition()


# ------------------------------------------------------------------------------------------------------------------------------ rows
def test_an_event_survives_the_trip_through_a_row():
    event = ev(7, "step", "summarizer", "running", "Reading", {"lane": "summarizer", "step": "digest", "done": 3, "groq": {"tokens": 10}, "queries": {"a": ["x", "y"]}})
    assert store.from_row(store.to_row(RUN, event)) == event
    assert store.to_row(RUN, event)["query_id"] == RUN and store.to_row(RUN, event)["event_at"] == event["timestamp"]


def test_a_row_holds_only_what_postgres_accepts():
    row = store.to_row(RUN, ev(1, "step", message="a\x00b", data={"n": float("nan"), "inf": float("inf"), "ok": 1.5, "path": Path("a"), "t": (1, 2)}))
    assert row["message"] == "ab"
    assert row["data"]["n"] is None and row["data"]["inf"] is None and row["data"]["ok"] == 1.5 and row["data"]["t"] == [1, 2]
    assert isinstance(row["data"]["path"], str)
    json.dumps(row, allow_nan=False)                                      # strict JSON, as the database requires


def test_a_row_with_json_text_in_data_is_read_back_as_a_dict():
    assert store.from_row({"seq": 1, "event": "step", "data": '{"a": 1}', "event_at": None})["data"] == {"a": 1}
    assert store.from_row({"seq": 1, "event": "step", "data": "not json", "event_at": None})["data"] == {}
    assert store.from_row({"seq": 1, "event": "step", "data": None, "event_at": None})["data"] == {}


# ----------------------------------------------------------------------------------------------------------------------------- writer
def test_the_writer_stores_every_event_in_batches():
    db = MemDb()
    s = store.RunEventStore(client=db, batch_size=2, flush_seconds=0.05)
    for e in a_finished_run():
        s.append(RUN, e)
    assert s.flush(5) and s.written == 6 and s.dropped == 0
    assert sorted(seq for _, seq in db.rows) == [0, 1, 2, 3, 4, 5]
    assert sum(db.batches) == 6 and max(db.batches) <= 2
    s.close()


def test_the_closing_event_is_written_at_once_without_a_flush():
    db = MemDb()
    s = store.RunEventStore(client=db, flush_seconds=60)                  # the writer would sleep a minute
    for e in a_finished_run():
        s.append(RUN, e)
    assert wait_for(lambda: len(db.rows) == 6), "run_completed must wake the writer"
    s.close()


def test_events_of_two_runs_do_not_mix():
    db = MemDb()
    s = store.RunEventStore(client=db, flush_seconds=0.05)
    other = "22222222-2222-2222-2222-222222222222"
    s.append(RUN, ev(0, "run_queued"))
    s.append(other, ev(0, "run_queued"))
    s.append(RUN, ev(1, "run_started"))
    assert s.flush(5) and set(db.rows) == {(RUN, 0), (RUN, 1), (other, 0)}
    s.close()


def test_writing_the_same_event_twice_keeps_one_row():
    db = MemDb()
    s = store.RunEventStore(client=db, flush_seconds=0.05)
    s.append(RUN, ev(1, "run_started"))
    s.append(RUN, ev(1, "run_started"))
    assert s.flush(5) and len(db.rows) == 1
    s.close()


def test_a_database_error_loses_that_batch_but_never_raises_and_the_writer_goes_on():
    db = MemDb()
    db.errors = [RuntimeError("boom")]
    s = store.RunEventStore(client=db, flush_seconds=0.05)
    s.append(RUN, ev(0, "run_queued"))
    assert s.flush(5) and s.dropped == 1 and not db.rows
    s.append(RUN, ev(1, "run_started"))
    assert s.flush(5) and s.written == 1 and list(db.rows) == [(RUN, 1)]
    s.close()


def test_a_dropped_connection_is_retried(monkeypatch):
    monkeypatch.setattr(store, "WRITE_DELAYS", (0, 0))
    db = MemDb()
    db.errors = [httpx.RemoteProtocolError("Server disconnected"), httpx.ConnectError("down")]
    s = store.RunEventStore(client=db, flush_seconds=0.05)
    s.append(RUN, ev(0, "run_queued"))
    assert s.flush(5) and s.written == 1 and s.dropped == 0 and db.calls == 3
    s.close()


def test_a_connection_that_stays_down_gives_up_after_three_tries(monkeypatch):
    monkeypatch.setattr(store, "WRITE_DELAYS", (0, 0))
    db = MemDb()
    db.errors = [httpx.ConnectError("down")] * 5
    s = store.RunEventStore(client=db, flush_seconds=0.05)
    s.append(RUN, ev(0, "run_queued"))
    assert s.flush(5) and s.dropped == 1 and db.calls == 3
    s.close()


def test_a_missing_table_is_a_warning_and_pauses_the_writes(caplog):
    db = MemDb()
    db.errors = [Exception("Could not find the table 'public.run_events' in the schema cache")]
    s = store.RunEventStore(client=db, flush_seconds=0.05)
    with caplog.at_level("WARNING", logger="apps.api.run_event_store"):
        s.append(RUN, ev(0, "run_queued"))
        assert s.flush(5)
        calls = db.calls
        s.append(RUN, ev(1, "run_started"))
        assert s.flush(5)
    assert db.calls == calls, "while paused the database is not asked again"
    assert sum("017_add_run_events.sql" in r.message for r in caplog.records) == 1
    s.close()


def test_a_malformed_event_does_not_lose_the_others():
    db = MemDb()
    s = store.RunEventStore(client=db, flush_seconds=0.05)
    s.append(RUN, {"event": "step"})                                      # no seq
    s.append(RUN, ev(1, "run_started"))
    assert s.flush(5) and s.dropped == 1 and list(db.rows) == [(RUN, 1)]
    s.close()


def test_close_writes_what_is_still_queued():
    db = MemDb()
    s = store.RunEventStore(client=db, flush_seconds=60)
    s.append(RUN, ev(0, "run_queued"))
    s.append(RUN, ev(1, "run_started"))
    s.close()
    assert len(db.rows) == 2


# ----------------------------------------------------------------------------------------------------------------------------- reads
def test_get_events_gives_the_stream_shape_in_order(monkeypatch):
    db = MemDb()
    monkeypatch.setattr(store, "supabase", db)
    for e in reversed(a_finished_run()):
        db.rows[(RUN, e["seq"])] = store.to_row(RUN, e)
    db.rows[("other", 0)] = store.to_row("other", ev(0, "run_queued"))
    assert REAL_GET_EVENTS(RUN) == a_finished_run()
    assert REAL_GET_EVENTS("nobody") == []


def test_get_events_reads_every_page(monkeypatch):
    db = MemDb()
    monkeypatch.setattr(store, "supabase", db)
    monkeypatch.setattr(store, "READ_PAGE", 4)
    events = [ev(i, "step", message=f"s{i}") for i in range(10)]
    for e in events:
        db.rows[(RUN, e["seq"])] = store.to_row(RUN, e)
    assert REAL_GET_EVENTS(RUN) == events and db.calls == 3               # 4 + 4 + 2 rows


def test_a_missing_table_reads_as_no_timeline(monkeypatch):
    db = MemDb()
    db.errors = [Exception("relation \"run_events\" does not exist (42P01)")] * 2
    monkeypatch.setattr(store, "supabase", db)
    assert REAL_GET_EVENTS(RUN) == [] and REAL_GET_RUN_TIMES(RUN) == {}


def test_a_dropped_connection_on_a_read_is_raised_for_the_routes_retry(monkeypatch):
    db = MemDb()
    db.errors = [httpx.RemoteProtocolError("Server disconnected")] * 2
    monkeypatch.setattr(store, "supabase", db)
    with pytest.raises(httpx.TransportError):
        REAL_GET_EVENTS(RUN)
    with pytest.raises(httpx.TransportError):
        REAL_GET_RUN_TIMES(RUN)


def test_run_times_come_from_the_start_and_the_closing_event(monkeypatch):
    db = MemDb()
    monkeypatch.setattr(store, "supabase", db)
    for e in a_finished_run():
        db.rows[(RUN, e["seq"])] = store.to_row(RUN, e)
    assert REAL_GET_RUN_TIMES(RUN) == {"startedAt": T.format(1), "finishedAt": T.format(5)}
    failed = "33333333-3333-3333-3333-333333333333"
    for e in (ev(0, "run_started"), ev(1, "run_failed", "summarizer", "failed", "RuntimeError: model server is down")):
        db.rows[(failed, e["seq"])] = store.to_row(failed, e)
    assert REAL_GET_RUN_TIMES(failed) == {"startedAt": T.format(0), "finishedAt": T.format(1), "error": "RuntimeError: model server is down"}
    assert REAL_GET_RUN_TIMES("nobody") == {}


# ---------------------------------------------------------------------------------------------------------------------------- replay
def test_replay_sends_the_stored_events_from_the_resume_point():
    stored = a_finished_run()
    assert store.replay(stored, 0, "completed", None, "/r") == stored
    assert [e["seq"] for e in store.replay(stored, 4, "completed", None, "/r")] == [4, 5]


def test_replay_sends_the_closing_event_again_to_a_client_that_is_past_the_end():
    stored = a_finished_run()
    assert store.replay(stored, 99, "completed", None, "/r") == [stored[-1]]


def test_a_run_cut_off_by_a_restart_gets_a_closing_event_that_names_the_running_stage():
    cut = a_finished_run()[:4] + [ev(4, "stage_started", "retrieval", "running")]        # planner finished, retrieval started, then the server stopped
    out = store.replay(cut, 0, "failed", None, "/r")
    assert [e["seq"] for e in out] == [0, 1, 2, 3, 4, 5]
    last = out[-1]
    assert last["event"] == "run_failed" and last["status"] == "failed" and last["stage"] == "retrieval"
    assert last["message"] == store.INTERRUPTED and last["timestamp"] == cut[-1]["timestamp"]
    only_planner = a_finished_run()[:4]                                   # planner done, nothing running: the closing event names no stage
    assert store.replay(only_planner, 0, "failed", "stopped by hand", "/r")[-1]["stage"] is None
    assert store.replay(only_planner, 0, "failed", "stopped by hand", "/r")[-1]["message"] == "stopped by hand"


def test_a_cut_off_run_that_the_database_calls_complete_is_closed_as_completed():
    cut = a_finished_run()[:5]
    last = store.replay(cut, 0, "completed", None, "/r")[-1]
    assert last["event"] == "run_completed" and last["data"] == {"reportUrl": "/r"} and last["stage"] is None


# ----------------------------------------------------------------------------------------------------- the run manager and the routes
class FakeGraph:
    def stream(self, state, stream_mode):
        sq = SimpleNamespace(main_topic="What are SSMs?", queries=["a", "b"])
        yield {"planner": {"task_plan": SimpleNamespace(sub_questions=[sq, sq], domain_anchor="deep learning")}}
        yield {"paper_retrieval": {"paper_results": [{}, {}, {}]}}
        yield {"web_search": {"web_sources": [{}, {}]}}
        yield {"summarizer": {"digests": [1, 2, 3], "coverage": {"a": {"sufficient": True}, "b": {"sufficient": False}}}}


QUESTION = "How do state space models compare with transformers?"


def finish(manager, run_id, seconds=5):
    assert wait_for(lambda: manager.get(run_id) is not None and manager.get(run_id).finished, seconds), "the run did not finish"
    return manager.get(run_id)


def test_every_event_of_a_run_reaches_the_table_and_reads_back_the_same(monkeypatch):
    db = MemDb()
    s = store.RunEventStore(client=db, flush_seconds=0.05)
    manager = rm.RunManager(graph_factory=lambda: FakeGraph(), max_workers=1, event_store=s)
    rec = finish(manager, manager.submit(QUESTION).id)
    assert s.flush(5)
    monkeypatch.setattr(store, "supabase", db)
    assert REAL_GET_EVENTS(rec.id) == rec.events and rec.events[-1]["event"] == "run_completed"
    assert {q for q, _ in db.rows} == {rec.id}, "the run id is the key"
    manager.shutdown()


def test_a_broken_store_never_fails_a_run():
    class Broken:
        def append(self, run_id, event):
            raise RuntimeError("store is down")

        def close(self):
            raise RuntimeError("cannot close")
    manager = rm.RunManager(graph_factory=lambda: FakeGraph(), max_workers=1, event_store=Broken())
    rec = finish(manager, manager.submit(QUESTION).id)
    assert rec.status == "completed" and rec.events[-1]["event"] == "run_completed"
    manager.shutdown()                                                    # must not raise either


def test_shutdown_closes_the_store():
    closed = threading.Event()
    manager = rm.RunManager(graph_factory=lambda: FakeGraph(), max_workers=1, event_store=SimpleNamespace(append=lambda r, e: None, close=closed.set))
    manager.shutdown()
    assert closed.is_set()


def test_without_a_store_the_manager_works_as_before():
    manager = rm.RunManager(graph_factory=lambda: FakeGraph(), max_workers=1)
    rec = finish(manager, manager.submit(QUESTION).id)
    assert rec.status == "completed"
    manager.shutdown()


def test_the_switch_is_on_unless_turned_off(monkeypatch):
    monkeypatch.delenv("RUN_EVENTS_STORE", raising=False)
    assert config.run_events_store_enabled() is True
    for value in ("false", "0", "off", "no"):
        monkeypatch.setenv("RUN_EVENTS_STORE", value)
        assert config.run_events_store_enabled() is False


@pytest.fixture
def client(monkeypatch):
    manager = rm.RunManager(graph_factory=lambda: FakeGraph(), max_workers=1)
    app.dependency_overrides[get_run_manager] = lambda: manager
    monkeypatch.setattr(report_service, "session_from_db", lambda qid: None)
    c = TestClient(app)
    c.manager = manager
    yield c
    app.dependency_overrides.clear()
    manager.shutdown()


def read_events(client, run_id, headers=None, query=""):
    events = []
    with client.stream("GET", f"/api/research/{run_id}/events{query}", headers=headers or {}) as r:
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
        for line in r.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


def test_a_run_that_is_not_in_memory_replays_its_whole_timeline(client, monkeypatch):
    monkeypatch.setattr(store, "get_events", lambda qid: a_finished_run())
    monkeypatch.setattr(report_service, "session_from_db", lambda qid: {"id": qid, "status": "completed", "error": None, "question": "q"})
    assert read_events(client, RUN) == a_finished_run()
    assert [e["seq"] for e in read_events(client, RUN, headers={"Last-Event-ID": "3"})] == [4, 5]
    assert [e["seq"] for e in read_events(client, RUN, query="?after=4")] == [5]


def test_a_timeline_is_replayed_even_when_the_run_has_no_plan_row(client, monkeypatch):
    """A run that failed in the planner never stored research_queries: its timeline is still there to read."""
    failed = [ev(0, "run_queued"), ev(1, "run_started"), ev(2, "stage_started", "planner", "running"),
              ev(3, "run_failed", "planner", "failed", "RuntimeError: the planner model is down")]
    monkeypatch.setattr(store, "get_events", lambda qid: failed)
    assert read_events(client, RUN) == failed                             # session_from_db answers None


def test_a_cut_off_run_is_closed_for_the_client_from_the_database_status(client, monkeypatch):
    monkeypatch.setattr(store, "get_events", lambda qid: a_finished_run()[:5])
    monkeypatch.setattr(report_service, "session_from_db", lambda qid: {"id": qid, "status": "failed", "error": store.INTERRUPTED, "question": "q"})
    events = read_events(client, RUN)
    assert [e["seq"] for e in events] == [0, 1, 2, 3, 4, 5] and events[-1]["event"] == "run_failed"


def test_a_run_without_a_stored_timeline_still_gets_its_one_closing_event(client, monkeypatch):
    monkeypatch.setattr(report_service, "session_from_db", lambda qid: {"id": qid, "status": "completed", "error": None, "question": "q"})
    events = read_events(client, RUN)                                     # get_events answers [] (a run from before migration 017)
    assert len(events) == 1 and events[0]["event"] == "run_completed" and events[0]["data"]["reportUrl"] == f"/api/research/{RUN}/report"


def test_an_unknown_run_is_still_404(client):
    assert client.get(f"/api/research/{RUN}/events").status_code == 404
    assert client.get("/api/research/not-a-uuid/events").status_code == 404


def test_a_live_run_is_still_served_from_memory(client, monkeypatch):
    monkeypatch.setattr(store, "get_events", lambda qid: pytest.fail("a run in memory must not read the table"))
    run_id = client.post("/api/research", json={"question": QUESTION}).json()["id"]
    finish(client.manager, run_id)
    events = read_events(client, run_id)
    assert events[0]["event"] == "run_queued" and events[-1]["event"] == "run_completed"


def test_the_session_of_a_stored_run_has_its_times(monkeypatch):
    class Table:
        def __init__(self, rows):
            self.rows = rows

        def select(self, *_):
            return self

        def eq(self, *_):
            return self

        def limit(self, *_):
            return self

        def execute(self):
            return SimpleNamespace(data=self.rows)

    tables = {"research_queries": [{"id": RUN, "raw_query": "q", "created_at": T.format(0)}], "sub_questions": [{"id": "sq1"}],
              "coverage_results": [{"sub_question_id": "sq1"}], "fact_claims": [], "written_reports": []}
    monkeypatch.setattr(report_service, "supabase", SimpleNamespace(table=lambda name: Table(tables.get(name, []))))
    monkeypatch.setattr(store, "get_run_times", lambda qid: {"startedAt": T.format(1), "finishedAt": T.format(5)})
    session = report_service.session_from_db(RUN)
    assert session["status"] == "completed" and session["startedAt"] == T.format(1) and session["finishedAt"] == T.format(5) and session["error"] is None
    tables["coverage_results"] = []                                       # not finished: failed, with the error that was stored
    monkeypatch.setattr(store, "get_run_times", lambda qid: {"startedAt": T.format(1), "finishedAt": T.format(3), "error": "RuntimeError: model server is down"})
    session = report_service.session_from_db(RUN)
    assert session["status"] == "failed" and session["error"] == "RuntimeError: model server is down"
    monkeypatch.setattr(store, "get_run_times", lambda qid: {})
    session = report_service.session_from_db(RUN)
    assert session["error"].startswith("The run did not finish") and session["startedAt"] is None
