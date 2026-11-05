"""NUL characters must never reach the database (Postgres 22P05 lost a parsed paper in the 2026-11-05 run)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.api.services import db_service  # noqa: E402

NUL = chr(0)


def has_nul(obj):
    """Look inside the strings: repr() shows a NUL as the four characters backslash-x-0-0, so searching a repr proves nothing."""
    if isinstance(obj, str):
        return NUL in obj
    if isinstance(obj, (list, tuple)):
        return any(has_nul(v) for v in obj)
    if isinstance(obj, dict):
        return any(has_nul(k) or has_nul(v) for k, v in obj.items())
    return False


def test_strip_nul_cleans_nested_values_and_keeps_the_rest():
    data = {"title": "a" + NUL + "b", "sections": [{"heading": "H" + NUL, "text": NUL + "body"}], "n": 3, "ok": None, "flag": True, "refs": ["x" + NUL + "y", "z"]}
    out = db_service.strip_nul(data)
    assert out == {"title": "ab", "sections": [{"heading": "H", "text": "body"}], "n": 3, "ok": None, "flag": True, "refs": ["xy", "z"]}
    assert has_nul(data) and not has_nul(out)               # the input is not modified, the output is clean


def test_strip_nul_returns_clean_strings_unchanged():
    s = "plain text"
    assert db_service.strip_nul(s) is s


class _FakeTable:
    def __init__(self, store, name):
        self.store, self.name = store, name

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def execute(self):
        class R:
            data = []
        return R()

    def insert(self, payload):
        self.store.append((self.name, "insert", payload))
        return self

    def update(self, payload):
        self.store.append((self.name, "update", payload))
        return self


class _FakeSupabase:
    def __init__(self):
        self.store = []

    def table(self, name):
        return _FakeTable(self.store, name)


@pytest.fixture
def fake_db(monkeypatch):
    fake = _FakeSupabase()
    monkeypatch.setattr(db_service, "supabase", fake)
    return fake


def _payload_has_nul(payload):
    return has_nul(payload)


def test_write_parsed_paper_stores_text_without_nul_and_logs_it(fake_db, caplog):
    with caplog.at_level("WARNING"):
        db_service.write_parsed_paper("p1", "T" + NUL, ["A" + NUL], "abs" + NUL, [{"heading": "h", "text": "t" + NUL}], ["r" + NUL], [], "full" + NUL + "text" + NUL, 1)
    kind, op, payload = fake_db.store[-1]
    assert kind == "parsed_papers" and not _payload_has_nul(payload) and payload["full_text"] == "fulltext"
    assert "Removed 2 NUL character(s)" in " ".join(r.getMessage() for r in caplog.records)


def test_other_text_writes_are_cleaned_too(fake_db):
    db_service.write_retrieved_papers("q", [{"title": "t" + NUL, "abstract": "a" + NUL, "sub_question_id": "s"}])
    db_service.write_digests([{"query_id": "q", "findings": [{"claim": "c" + NUL, "quote": "q" + NUL}]}])
    db_service.write_coverage([{"query_id": "q", "uncovered_details": ["d" + NUL]}])
    assert len(fake_db.store) == 3 and not any(_payload_has_nul(p) for _, _, p in fake_db.store)


def test_web_sources_are_cleaned(fake_db):
    class S:
        sub_question_id, url, title, snippet, published_date, provider, reliability_score = "s", "u", "t" + NUL, "snip" + NUL, None, "tavily", 0.5
    db_service.write_web_sources([S()])
    assert not _payload_has_nul(fake_db.store[-1][2]) and fake_db.store[-1][2][0]["snippet"] == "snip"
