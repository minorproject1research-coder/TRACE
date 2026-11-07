"""The pipeline's own database calls survive a dropped connection (planned item B8). Offline: a fake Supabase client."""
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.api.services import db_errors, db_service  # noqa: E402


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(db_errors.time, "sleep", lambda s: None)


def flaky(errors, result="ok"):
    calls = {"n": 0}

    @db_errors.retry_transient
    def fn():
        calls["n"] += 1
        if calls["n"] <= len(errors):
            raise errors[calls["n"] - 1]
        return result
    return fn, calls


def test_succeeds_after_two_dropped_connections():
    fn, calls = flaky([httpx.RemoteProtocolError("Server disconnected"), httpx.WriteError("EOF occurred in violation of protocol")])
    assert fn() == "ok"
    assert calls["n"] == 3


def test_raises_the_original_error_after_the_last_attempt():
    fn, calls = flaky([httpx.RemoteProtocolError("a")] * 5)
    with pytest.raises(httpx.RemoteProtocolError):
        fn()
    assert calls["n"] == db_errors.TRANSIENT_ATTEMPTS


def test_other_errors_are_not_retried():
    fn, calls = flaky([ValueError("bad column")])
    with pytest.raises(ValueError):
        fn()
    assert calls["n"] == 1


def test_no_retry_when_the_call_works():
    fn, calls = flaky([])
    assert fn() == "ok" and calls["n"] == 1


class FakeTable:
    """parsed_papers with a connection that dies AFTER the insert reached the server (the response is lost)."""
    def __init__(self, client):
        self.client, self.store = client, client.store
        self.op = None

    def select(self, *a):
        self.op = ("select",)
        return self

    def eq(self, col, val):
        self.val = val
        return self

    def insert(self, row):
        self.op = ("insert", row)
        return self

    def update(self, row):
        self.op = ("update", row)
        return self

    def execute(self):
        class R:
            data = []
        r = R()
        if self.op[0] == "select":
            r.data = [{"id": 1}] if self.val in self.store else []
        elif self.op[0] == "insert":
            self.store[self.op[1]["retrieved_paper_id"]] = self.op[1]
            if self.client.drop:
                self.client.drop -= 1
                raise httpx.RemoteProtocolError("<ConnectionTerminated error_code:9>")
        elif self.op[0] == "update":
            self.store[self.val].update(self.op[1])
        return r


class FakeClient:
    def __init__(self, drop_after_insert):
        self.store = {}
        self.drop = drop_after_insert

    def table(self, name):
        return FakeTable(self)


def test_parsed_paper_is_stored_once_when_the_insert_response_is_lost(monkeypatch):
    client = FakeClient(drop_after_insert=1)
    monkeypatch.setattr(db_service, "supabase", client)
    db_service._upsert_parsed("paper-1", {"title": "T", "full_text": "x" * 10})
    assert list(client.store) == ["paper-1"]                      # retried as an update, no duplicate insert
    assert client.store["paper-1"]["title"] == "T"
