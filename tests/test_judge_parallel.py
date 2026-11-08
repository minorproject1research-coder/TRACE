"""JUDGE_PARALLEL: Stage 3 judge batches sent to the host at the same time give the same result as one after the other.

All offline: `_call_judge_batch` is replaced by a fake; no request leaves the machine.
"""
import threading
import time

import httpx
import pytest

from apps.api.agents.stage3_summarizer import evidence_judge as ej


def _items(n):
    return [{"id": f"a0_s{i}_f0", "aspect_idx": 0, "source_id": f"s{i}", "aspect": "how it works",
             "claim": f"claim {i}", "quote": f"quote {i}", "context": ""} for i in range(n)]


def _verdict_for(item):
    n = int(item["claim"].split()[-1])
    return {"verdict": {"final": ["yes", "partial", "no"][n % 3], "quote_supports_claim": "yes",
                        "answers_aspect": "yes", "reason": item["claim"]},
            "raw_output": f"raw {n}", "error": None}


_REAL_SLEEP = time.sleep


@pytest.fixture(autouse=True)
def _setup(monkeypatch):
    monkeypatch.setenv("JUDGE_URL", "http://test-judge")
    monkeypatch.setenv("JUDGE_BATCH_SIZE", "4")
    monkeypatch.setenv("JUDGE_RETRIES", "2")
    monkeypatch.setattr(ej.time, "sleep", lambda s: None)      # retry back-off costs no test time


def _run(monkeypatch, parallel, fake, n=18, fresh=True):
    if fresh and ej.JUDGE_CACHE_PATH.exists():                 # every run starts with an empty cache unless the test wants the old one
        ej.JUDGE_CACHE_PATH.unlink()
    monkeypatch.setenv("JUDGE_PARALLEL", str(parallel))
    monkeypatch.setattr(ej, "_call_judge_batch", fake)
    return ej.judge_candidates(_items(n))


def _ok_fake(items, url, key, timeout):
    _REAL_SLEEP(0.01)
    return [_verdict_for(i) for i in items]


def test_default_is_two_and_bad_values_mean_one(monkeypatch):
    monkeypatch.delenv("JUDGE_PARALLEL", raising=False)
    assert ej._get_config()["JUDGE_PARALLEL"] == 2
    for bad, want in (("1", 1), ("3", 3), ("0", 1), ("-4", 1), ("abc", 1), ("", 1)):
        monkeypatch.setenv("JUDGE_PARALLEL", bad)
        assert ej._get_config()["JUDGE_PARALLEL"] == want


@pytest.mark.parametrize("workers", [2, 3, 8])
def test_same_result_and_order_as_sequential(monkeypatch, workers):
    seq = _run(monkeypatch, 1, _ok_fake)
    par = _run(monkeypatch, workers, _ok_fake)
    assert len(seq) == 18
    assert par == seq
    assert list(par.keys()) == list(seq.keys())


def test_batches_really_overlap_with_workers_and_not_with_one(monkeypatch):
    state = {"now": 0, "max": 0}
    lock = threading.Lock()

    def fake(items, url, key, timeout):
        with lock:
            state["now"] += 1
            state["max"] = max(state["max"], state["now"])
        _REAL_SLEEP(0.05)
        with lock:
            state["now"] -= 1
        return [_verdict_for(i) for i in items]

    _run(monkeypatch, 1, fake)
    assert state["max"] == 1
    state["max"] = 0
    _run(monkeypatch, 3, fake)
    assert 2 <= state["max"] <= 3


def test_batch_contents_are_the_same_slices(monkeypatch):
    seen = []

    def fake(items, url, key, timeout):
        seen.append(tuple(i["id"] for i in items))
        return [_verdict_for(i) for i in items]

    _run(monkeypatch, 1, fake)
    seq_batches = list(seen)
    seen.clear()
    _run(monkeypatch, 3, fake)
    assert sorted(seen) == sorted(seq_batches)
    assert sorted(len(b) for b in seq_batches) == [2, 4, 4, 4, 4]


@pytest.mark.parametrize("workers", [1, 3])
def test_retry_works_per_batch(monkeypatch, workers):
    attempts = {}
    lock = threading.Lock()

    def fake(items, url, key, timeout):
        first = items[0]["id"]
        with lock:
            attempts[first] = attempts.get(first, 0) + 1
            n = attempts[first]
        if first == "a0_s4_f0" and n < 3:                      # the second batch fails twice, then answers
            raise httpx.ConnectError("boom")
        return [_verdict_for(i) for i in items]

    out = _run(monkeypatch, workers, fake)
    assert attempts["a0_s4_f0"] == 3
    assert attempts["a0_s0_f0"] == 1 and attempts["a0_s8_f0"] == 1
    assert all(v["verdict"]["final"] != "error" for v in out.values())
    assert len(out) == 18


@pytest.mark.parametrize("workers", [1, 3])
def test_failing_batch_does_not_lose_the_others(monkeypatch, workers):
    def fake(items, url, key, timeout):
        if items[0]["id"] == "a0_s4_f0":                       # always down
            raise httpx.TimeoutException("slow")
        return [_verdict_for(i) for i in items]

    out = _run(monkeypatch, workers, fake)
    assert len(out) == 18
    bad = [k for k, v in out.items() if v["verdict"]["final"] == "error"]
    assert len(bad) == 4
    assert {k[1] for k in bad} == {"s4", "s5", "s6", "s7"}
    good = [v for k, v in out.items() if k[1] not in {"s4", "s5", "s6", "s7"}]
    assert all(v["verdict"]["final"] in ("yes", "partial", "no") for v in good)
    # only the good verdicts reach the cache
    cache = ej._load_judge_cache()
    assert len(cache) == 14


def test_failure_result_identical_for_one_and_many_workers(monkeypatch):
    def fake(items, url, key, timeout):
        if items[0]["id"] == "a0_s8_f0":
            raise httpx.ConnectError("down")
        return [_verdict_for(i) for i in items]

    seq = _run(monkeypatch, 1, fake)
    par = _run(monkeypatch, 3, fake)
    assert par == seq


def test_short_answer_from_the_server_is_padded_with_errors(monkeypatch):
    def fake(items, url, key, timeout):
        return [_verdict_for(i) for i in items][:-1] if items[0]["id"] == "a0_s0_f0" else [_verdict_for(i) for i in items]

    seq = _run(monkeypatch, 1, fake)
    par = _run(monkeypatch, 3, fake)
    assert par == seq
    assert sum(v["verdict"]["final"] == "error" for v in par.values()) == 1


@pytest.mark.parametrize("workers", [1, 3])
def test_cache_hits_are_not_sent_and_new_verdicts_are_cached(monkeypatch, workers):
    first_sent = []

    def fake1(items, url, key, timeout):
        first_sent.extend(i["id"] for i in items)
        return [_verdict_for(i) for i in items]

    out1 = _run(monkeypatch, workers, fake1, n=10)
    assert len(first_sent) == 10 and len(ej._load_judge_cache()) == 10

    sent = []

    def fake2(items, url, key, timeout):
        sent.extend(i["id"] for i in items)
        return [_verdict_for(i) for i in items]

    out2 = _run(monkeypatch, workers, fake2, n=14, fresh=False)  # 10 cached, 4 new
    assert sorted(sent) == sorted(f"a0_s{i}_f0" for i in range(10, 14))
    assert {k: v for k, v in out2.items() if k in out1} == out1
    assert len(out2) == 14

    sent.clear()
    out3 = _run(monkeypatch, workers, fake2, n=14, fresh=False)  # everything cached: no call at all
    assert sent == [] and out3 == out2


def test_single_batch_and_no_items_with_many_workers(monkeypatch):
    out = _run(monkeypatch, 3, _ok_fake, n=3)
    assert len(out) == 3
    assert _run(monkeypatch, 3, _ok_fake, n=0) == {}
