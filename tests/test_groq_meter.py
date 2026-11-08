"""The Groq token meter (apps/api/services/groq_pool.py): counts tokens per call, purpose and key, keeps the rate-limit headers, writes a log."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from apps.api.services import groq_pool  # noqa: E402


def usage(prompt, completion, reasoning=0):
    return SimpleNamespace(prompt_tokens=prompt, completion_tokens=completion, total_tokens=prompt + completion,
                           completion_tokens_details=SimpleNamespace(reasoning_tokens=reasoning))


class FakeRaw:
    def __init__(self, u, headers):
        self._u, self.headers = u, headers

    def parse(self):
        return SimpleNamespace(usage=self._u, choices=[SimpleNamespace(message=SimpleNamespace(content="{}"))])


class FakeClient:
    def __init__(self, u, headers):
        create = lambda **kw: FakeRaw(u, headers)                                    # noqa: E731
        self.chat = SimpleNamespace(completions=SimpleNamespace(with_raw_response=SimpleNamespace(create=create)))


@pytest.fixture
def pool(monkeypatch, tmp_path):
    monkeypatch.setattr(groq_pool, "USAGE_LOG", str(tmp_path / "usage.jsonl"))
    monkeypatch.setattr(groq_pool, "meter", groq_pool.UsageMeter())
    p = groq_pool.GroqPool(["key-aaaa1111", "key-bbbb2222"])
    headers = {"x-ratelimit-limit-requests": "1000", "x-ratelimit-remaining-requests": "990", "x-ratelimit-limit-tokens": "8000",
               "x-ratelimit-remaining-tokens": "5000"}
    p._clients = {k: FakeClient(usage(1000, 300, 200), headers) for k in p._keys}
    return p


def test_every_call_is_counted_by_purpose_and_key(pool):
    snap = groq_pool.meter.snapshot()
    pool.chat([{"role": "user", "content": "x"}], "m", purpose="digest")
    pool.chat([{"role": "user", "content": "x"}], "m", purpose="digest")
    pool.chat([{"role": "user", "content": "x"}], "m", purpose="stage4_judge")
    used = groq_pool.meter.since(snap)
    assert used["totals"] == {"calls": 3, "prompt": 3000, "completion": 900, "reasoning": 600, "total": 3900}
    assert used["by_purpose"]["digest"]["total"] == 2600 and used["by_purpose"]["stage4_judge"]["calls"] == 1
    assert sorted(used["by_key"]) == ["1111", "2222"] and sum(c["calls"] for c in used["by_key"].values()) == 3        # spread over both keys


def test_the_response_is_the_normal_completion_object(pool):
    r = pool.chat([{"role": "user", "content": "x"}], "m")
    assert r.choices[0].message.content == "{}" and r.usage.total_tokens == 1300


def test_since_counts_only_what_came_after_the_snapshot(pool):
    pool.chat([{"role": "user", "content": "x"}], "m", purpose="digest")
    snap = groq_pool.meter.snapshot()
    pool.chat([{"role": "user", "content": "x"}], "m", purpose="aspect_split")
    used = groq_pool.meter.since(snap)
    assert used["totals"]["calls"] == 1 and list(used["by_purpose"]) == ["aspect_split"]


def test_the_rate_limit_headers_and_429s_are_kept(pool):
    pool.chat([{"role": "user", "content": "x"}], "m")
    limits = groq_pool.meter.limits
    assert {v["limit-requests"] for v in limits.values()} == {"1000"} and {v["limit-tokens"] for v in limits.values()} == {"8000"}
    groq_pool.meter.rate_limited("key-aaaa1111", "digest", 12.0)
    assert groq_pool.meter.totals["rate_limited"] == 1 and groq_pool.meter.by_key["1111"]["rate_limited"] == 1


def test_a_log_line_is_written_per_call_and_per_429(pool, tmp_path):
    pool.chat([{"role": "user", "content": "x"}], "m", purpose="digest")
    groq_pool.meter.rate_limited("key-bbbb2222", "digest", 5.0)
    lines = [json.loads(l) for l in (tmp_path / "usage.jsonl").read_text(encoding="utf-8").splitlines()]
    assert lines[0]["purpose"] == "digest" and lines[0]["total"] == 1300 and lines[0]["reasoning"] == 200 and lines[0]["rl_limit_tokens"] == "8000"
    assert lines[1]["event"] == "429" and lines[1]["parked_seconds"] == 5


def test_logging_can_be_switched_off_and_never_breaks_a_call(pool, monkeypatch, tmp_path):
    monkeypatch.setattr(groq_pool, "USAGE_LOG", "off")
    pool.chat([{"role": "user", "content": "x"}], "m")
    assert not (tmp_path / "usage.jsonl").exists()
    monkeypatch.setattr(groq_pool, "USAGE_LOG", str(tmp_path / "nodir" / "x" / "\0bad"))      # an unwritable path
    assert pool.chat([{"role": "user", "content": "x"}], "m").usage.total_tokens == 1300


def test_a_reply_without_usage_does_not_break_counting(pool):
    pool._clients = {k: FakeClient(None, None) for k in pool._keys}
    assert pool.chat([{"role": "user", "content": "x"}], "m").choices
    assert groq_pool.meter.totals["calls"] == 1 and groq_pool.meter.totals["total"] == 0


def test_the_usage_line_is_readable():
    text = groq_pool.usage_text({"totals": {"total": 4200, "prompt": 3000, "completion": 1200, "reasoning": 800, "calls": 3, "rate_limited": 2},
                                 "by_purpose": {"digest": {"total": 3000}, "stage4_judge": {"total": 1200}}})
    assert "4,200 tokens" in text and "800 reasoning" in text and "3 calls" in text and "2 rate limits" in text and "digest 3,000" in text
