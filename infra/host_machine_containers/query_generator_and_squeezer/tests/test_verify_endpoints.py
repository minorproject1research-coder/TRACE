"""Tests for /verify_evidence and /verify_evidence_batch.

No vLLM server or model files are needed: vllm_post is replaced by a fake and the
tokenizer is stubbed out.

Run from the project folder:
    pip install pytest fastapi httpx pydantic      (once)
    pytest tests/test_verify_endpoints.py -v
"""
import importlib
import json
import re
import sys
import time
import types
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
KEY = "test-key"
HEADERS = {"x-api-key": KEY}
ANS = ["yes", "partial", "no"]

# final = yes only if both yes; no if either no; otherwise partial
EXPECTED_FINAL = {
    ("yes", "yes"): "yes", ("yes", "partial"): "partial", ("yes", "no"): "no",
    ("partial", "yes"): "partial", ("partial", "partial"): "partial", ("partial", "no"): "no",
    ("no", "yes"): "no", ("no", "partial"): "no", ("no", "no"): "no",
}
SINGLE = {"aspect": "an aspect", "claim": "a claim", "quote": "a quote"}


@pytest.fixture(scope="module")
def m():
    """Import main.py with the tokenizer stubbed (the real one needs the model folder)."""
    stub = types.ModuleType("transformers")

    class _Tok:
        @classmethod
        def from_pretrained(cls, *args, **kwargs):
            return cls()

        def apply_chat_template(self, *args, **kwargs):
            return ""

    stub.AutoTokenizer = _Tok
    saved = sys.modules.get("transformers")
    sys.modules["transformers"] = stub
    sys.path.insert(0, str(ROOT))
    sys.modules.pop("main", None)
    mod = importlib.import_module("main")
    try:
        yield mod
    finally:
        sys.path.remove(str(ROOT))
        sys.modules.pop("main", None)
        if saved is None:
            sys.modules.pop("transformers", None)
        else:
            sys.modules["transformers"] = saved


@pytest.fixture
def client(m, monkeypatch):
    monkeypatch.setattr(m, "API_KEY", KEY)
    return TestClient(m.app)


def reply(content):
    return {"choices": [{"message": {"content": content}}]}


def verdict_json(q, a, reason="ok", **extra):
    return json.dumps({"quote_supports_claim": q, "answers_aspect": a, "reason": reason, **extra})


def patch_vllm(monkeypatch, m, fn):
    monkeypatch.setattr(m, "vllm_post", fn)


# ------------------------------------------------------------------ verdict + final
@pytest.mark.parametrize("q,a", [(q, a) for q in ANS for a in ANS])
def test_final_for_all_nine_combinations(client, m, monkeypatch, q, a):
    # the model also claims final="yes"; it must be ignored and recomputed in code
    patch_vllm(monkeypatch, m, lambda path, payload: reply(verdict_json(q, a, final="yes")))
    r = client.post("/verify_evidence", json=SINGLE, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["verdict"] == {
        "quote_supports_claim": q, "answers_aspect": a,
        "final": EXPECTED_FINAL[(q, a)], "reason": "ok"}


def test_answers_are_normalized_to_lowercase(client, m, monkeypatch):
    patch_vllm(monkeypatch, m, lambda path, payload: reply(verdict_json(" YES ", "Partial")))
    v = client.post("/verify_evidence", json=SINGLE, headers=HEADERS).json()["verdict"]
    assert (v["quote_supports_claim"], v["answers_aspect"], v["final"]) == ("yes", "partial", "partial")


def test_missing_reason_defaults_to_empty_string(client, m, monkeypatch):
    raw = json.dumps({"quote_supports_claim": "no", "answers_aspect": "no"})
    patch_vllm(monkeypatch, m, lambda path, payload: reply(raw))
    v = client.post("/verify_evidence", json=SINGLE, headers=HEADERS).json()["verdict"]
    assert v["reason"] == "" and v["final"] == "no"


@pytest.mark.parametrize("raw", [
    "<think>\nhmm {not the answer}\n</think>\n```json\n" + verdict_json("yes", "partial", "r") + "\n```",
    "Sure! Here you go:\n```json\n" + verdict_json("yes", "partial", "r") + "\n```\nHope that helps.",
    "<think>x</think>" + verdict_json("yes", "partial", "r"),
])
def test_think_blocks_fences_and_prose_are_tolerated(client, m, monkeypatch, raw):
    patch_vllm(monkeypatch, m, lambda path, payload: reply(raw))
    body = client.post("/verify_evidence", json=SINGLE, headers=HEADERS).json()
    assert body["verdict"] == {"quote_supports_claim": "yes", "answers_aspect": "partial",
                               "final": "partial", "reason": "r"}
    assert body["raw_output"] == raw.strip()


@pytest.mark.parametrize("raw", [
    "I cannot answer that.",
    "",
    verdict_json("maybe", "yes"),
    verdict_json("yes", "sort of"),
    json.dumps({"quote_supports_claim": "yes"}),
    json.dumps({"quote_supports_claim": True, "answers_aspect": "yes"}),
    json.dumps(["yes", "yes"]),
    '{"quote_supports_claim": "yes", "answers_aspect": ',
    '{"quote_supports_claim": "yes", "answers_aspect": "no", "reason": "The quote supp',  # cut off mid-sentence
    '{"quote_supports_claim": "maybe", "answers_aspect": "no", "reason": "x"',  # missing brace AND invalid value
])
def test_garbage_or_invalid_values_give_null_verdict(client, m, monkeypatch, raw):
    patch_vllm(monkeypatch, m, lambda path, payload: reply(raw))
    r = client.post("/verify_evidence", json=SINGLE, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["verdict"] is None
    assert r.json()["raw_output"] == raw.strip()


@pytest.mark.parametrize("raw,expected", [
    # real replies from the served model: complete JSON except for the final closing brace
    ('{"quote_supports_claim": "no", "answers_aspect": "no", "reason": "The quote is merely a table headerand does not define or state the meaning of memory cost."',
     ("no", "no", "no")),
    ('{"quote_supports_claim": "yes", "answers_aspect": "partial", "reason": "The quote supports the claimbut only addresses visual language models."',
     ("yes", "partial", "partial")),
    ('```json\n{"quote_supports_claim": "yes", "answers_aspect": "yes", "reason": "ok"\n```',
     ("yes", "yes", "yes")),
])
def test_reply_missing_only_the_closing_brace_is_accepted(client, m, monkeypatch, raw, expected):
    patch_vllm(monkeypatch, m, lambda path, payload: reply(raw))
    body = client.post("/verify_evidence", json=SINGLE, headers=HEADERS).json()
    v = body["verdict"]
    assert (v["quote_supports_claim"], v["answers_aspect"], v["final"]) == expected
    assert body["raw_output"] == raw.strip()


def test_vllm_failure_is_502_for_single_item(client, m, monkeypatch):
    def boom(path, payload):
        raise HTTPException(502, "vLLM unreachable")
    patch_vllm(monkeypatch, m, boom)
    assert client.post("/verify_evidence", json=SINGLE, headers=HEADERS).status_code == 502


# ------------------------------------------------------------------ batch
def test_batch_preserves_order_and_ids(client, m, monkeypatch):
    def fake(path, payload):
        idx = int(re.search(r"Claim: c(\d+)", payload["messages"][0]["content"]).group(1))
        time.sleep(0.01 * (9 - idx))  # earlier items finish last
        return reply(verdict_json(ANS[idx % 3], "yes", f"r{idx}"))
    patch_vllm(monkeypatch, m, fake)
    items = [{"id": f"id-{i}", "aspect": "x", "claim": f"c{i}", "quote": "q"} for i in range(10)]
    r = client.post("/verify_evidence_batch", json={"items": items}, headers=HEADERS)
    assert r.status_code == 200
    results = r.json()["results"]
    assert [x["id"] for x in results] == [f"id-{i}" for i in range(10)]
    for i, x in enumerate(results):
        assert x["error"] is None
        assert x["verdict"]["quote_supports_claim"] == ANS[i % 3]
        assert x["verdict"]["reason"] == f"r{i}"


def test_one_failing_item_does_not_fail_the_batch(client, m, monkeypatch):
    def fake(path, payload):
        prompt = payload["messages"][0]["content"]
        if "Claim: http-fail" in prompt:
            raise HTTPException(502, "boom")
        if "Claim: crash" in prompt:
            raise RuntimeError("kaput")
        if "Claim: garbage" in prompt:
            return reply("no json here")
        return reply(verdict_json("yes", "yes"))
    patch_vllm(monkeypatch, m, fake)
    claims = ["fine-1", "http-fail", "crash", "garbage", "fine-2"]
    items = [{"id": c, "aspect": "x", "claim": c, "quote": "q"} for c in claims]
    r = client.post("/verify_evidence_batch", json={"items": items}, headers=HEADERS)
    assert r.status_code == 200
    by_id = {x["id"]: x for x in r.json()["results"]}
    assert [x["id"] for x in r.json()["results"]] == claims
    assert by_id["fine-1"]["verdict"]["final"] == "yes" and by_id["fine-1"]["error"] is None
    assert by_id["fine-2"]["verdict"]["final"] == "yes"
    assert by_id["http-fail"]["verdict"] is None and "boom" in by_id["http-fail"]["error"]
    assert by_id["crash"]["verdict"] is None and "kaput" in by_id["crash"]["error"]
    assert by_id["garbage"]["verdict"] is None and by_id["garbage"]["raw_output"] == "no json here"
    assert by_id["garbage"]["error"] is None


def test_batch_larger_than_limit_is_422(client, m, monkeypatch):
    patch_vllm(monkeypatch, m, lambda path, payload: reply(verdict_json("yes", "yes")))
    item = {"id": "i", "aspect": "x", "claim": "c", "quote": "q"}
    too_many = {"items": [item] * (m.MAX_VERIFY_ITEMS + 1)}
    assert client.post("/verify_evidence_batch", json=too_many, headers=HEADERS).status_code == 422
    exactly = {"items": [item] * m.MAX_VERIFY_ITEMS}
    assert client.post("/verify_evidence_batch", json=exactly, headers=HEADERS).status_code == 200


# ------------------------------------------------------------------ auth
@pytest.mark.parametrize("headers", [{}, {"x-api-key": "wrong"}])
def test_missing_or_wrong_key_is_401_on_both_endpoints(client, m, monkeypatch, headers):
    def must_not_run(path, payload):
        raise AssertionError("vLLM must not be called without a valid key")
    patch_vllm(monkeypatch, m, must_not_run)
    batch = {"items": [{"id": "i", "aspect": "x", "claim": "c", "quote": "q"}]}
    assert client.post("/verify_evidence", json=SINGLE, headers=headers).status_code == 401
    assert client.post("/verify_evidence_batch", json=batch, headers=headers).status_code == 401


# ------------------------------------------------------------------ prompt + request
def test_long_fields_are_truncated_before_the_prompt_is_built(client, m, monkeypatch):
    seen = []

    def fake(path, payload):
        seen.append(payload)
        return reply(verdict_json("yes", "yes"))
    patch_vllm(monkeypatch, m, fake)
    body = {"aspect": "µ" * 5000, "claim": "§" * 5000, "quote": "‡" * 5000, "context": "¶" * 5000}
    client.post("/verify_evidence", json=body, headers=HEADERS)
    client.post("/verify_evidence_batch", json={"items": [{"id": "1", **body}]}, headers=HEADERS)
    assert len(seen) == 2
    for payload in seen:
        prompt = payload["messages"][0]["content"]
        assert prompt.count("µ") == m.MAX_FIELD_CHARS
        assert prompt.count("§") == m.MAX_FIELD_CHARS
        assert prompt.count("‡") == m.MAX_FIELD_CHARS
        assert prompt.count("¶") == m.MAX_CONTEXT_CHARS


def test_braces_in_user_text_do_not_break_the_prompt(client, m, monkeypatch):
    seen = []
    patch_vllm(monkeypatch, m, lambda path, payload: (seen.append(payload), reply(verdict_json("yes", "yes")))[1])
    body = {"aspect": "a {x}", "claim": "uses {braces} and {{double}}", "quote": "{q}", "context": "{c}"}
    r = client.post("/verify_evidence", json=body, headers=HEADERS)
    assert r.status_code == 200
    assert "uses {braces} and {{double}}" in seen[0]["messages"][0]["content"]


def test_request_to_vllm_is_built_like_judge(client, m, monkeypatch):
    seen = []
    patch_vllm(monkeypatch, m, lambda path, payload: (seen.append((path, payload)), reply(verdict_json("yes", "yes")))[1])
    client.post("/verify_evidence", json=SINGLE, headers=HEADERS)
    client.post("/verify_evidence", json={**SINGLE, "max_new_tokens": 50, "thinking": True}, headers=HEADERS)
    (path1, p1), (path2, p2) = seen
    assert path1 == path2 == "/v1/chat/completions"
    assert p1["model"] == m.JUDGE_MODEL and p1["temperature"] == 0.0
    assert p1["max_tokens"] == 200 and p1["chat_template_kwargs"] == {"enable_thinking": False}
    assert p1["messages"][0]["role"] == "user" and len(p1["messages"]) == 1
    assert p2["max_tokens"] == 50 and p2["chat_template_kwargs"] == {"enable_thinking": True}


# ------------------------------------------------------------------ existing endpoint untouched
def test_existing_judge_endpoint_still_works(client, m, monkeypatch):
    raw = json.dumps({"relevant": True, "confidence": 0.8, "reason": "r"})
    patch_vllm(monkeypatch, m, lambda path, payload: reply(raw))
    body = {"sub_question": "q", "title": "t", "abstract": "a"}
    r = client.post("/judge", json=body, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["verdict"] == {"relevant": True, "confidence": 0.8, "reason": "r"}
