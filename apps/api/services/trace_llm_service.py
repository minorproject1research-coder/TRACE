# apps/api/services/trace_llm_service.py
"""Client for the TRACE model server.

One FastAPI wrapper (reached over Tailscale) sits in front of one vLLM server that hosts two roles on the same
Qwen3.5-9B weights: "planner" (LoRA fine-tune, POST /decompose) and "judge" (base model, POST /judge).
Every endpoint needs the x-api-key header.

Environment:
  TRACE_LLM_URL                   server address (default https://mllab.tail0f44aa.ts.net)
  TRACE_LLM_API_KEY  or  x-api-key   the API key (either name works)
  TRACE_LLM_TIMEOUT_SECONDS       per-request timeout (default 240; /decompose takes 15-30 s)
"""
import json
import logging
import os
import threading
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("apps.api.services.trace_llm")

DEFAULT_URL = "https://mllab.tail0f44aa.ts.net"
RETRYABLE_STATUS = (429, 500, 502, 503, 504)
UNAVAILABLE_COOLDOWN_SECONDS = 60       # after a connection failure, fail fast instead of waiting on every call


class TraceLLMError(Exception):
    """The model server could not be used (unreachable, rejected the key, or returned unusable output)."""


_client: httpx.Client | None = None
_client_lock = threading.Lock()
_unavailable_until = 0.0


def base_url() -> str:
    return os.getenv("TRACE_LLM_URL", DEFAULT_URL).rstrip("/")


def _api_key() -> str:
    for name in ("TRACE_LLM_API_KEY", "x-api-key", "X_API_KEY"):
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _get_client() -> httpx.Client:
    global _client
    with _client_lock:
        if _client is None:
            timeout = float(os.getenv("TRACE_LLM_TIMEOUT_SECONDS", "240"))
            _client = httpx.Client(timeout=httpx.Timeout(timeout, connect=15.0))
        return _client


def _request(method: str, path: str, payload: dict | None = None, retries: int = 3) -> dict:
    global _unavailable_until
    key = _api_key()
    if not key:
        raise TraceLLMError("no API key: set TRACE_LLM_API_KEY (or x-api-key) in .env")
    if time.time() < _unavailable_until:
        raise TraceLLMError(f"model server at {base_url()} is marked unavailable (recent connection failures)")

    url = f"{base_url()}{path}"
    last_error = ""
    for attempt in range(retries):
        try:
            resp = _get_client().request(method, url, json=payload, headers={"x-api-key": key})
        except httpx.TransportError as e:           # unreachable, timeout, connection reset
            last_error = f"{type(e).__name__}: {str(e)[:120]}"
        else:
            if resp.status_code in (401, 403):
                raise TraceLLMError(f"model server rejected the API key (HTTP {resp.status_code})")
            if resp.status_code in RETRYABLE_STATUS:
                last_error = f"HTTP {resp.status_code}"
            elif resp.status_code >= 400:
                raise TraceLLMError(f"{path} returned HTTP {resp.status_code}: {resp.text[:200]}")
            else:
                try:
                    return resp.json()
                except ValueError as e:
                    raise TraceLLMError(f"{path} returned non-JSON: {resp.text[:200]}") from e
        if attempt < retries - 1:
            time.sleep(2 ** attempt * 2)

    if "HTTP" not in last_error:                    # connection-level failure: stop hammering a dead server
        _unavailable_until = time.time() + UNAVAILABLE_COOLDOWN_SECONDS
    raise TraceLLMError(f"{path} failed after {retries} attempts ({last_error})")


def extract_json_from_output(raw_output: str):
    """First JSON object in a model reply, or None (tolerates text before it and after it)."""
    raw_output = (raw_output or "").strip()
    decoder = json.JSONDecoder()
    start = raw_output.find("{")
    if start == -1:
        return None
    try:
        obj, _ = decoder.raw_decode(raw_output[start:])
        return obj
    except json.JSONDecodeError:
        return None


def extract_json_repairing(raw_output: str):
    """Like extract_json_from_output, but also repairs a reply that stops right after its last string.

    The judge endpoint occasionally returns a complete verdict that is missing only the final "}" (28 of 360 replies in
    a benchmark run, always the same defect), so a few closers are tried before giving up."""
    obj = extract_json_from_output(raw_output)
    if obj is not None:
        return obj
    text = (raw_output or "").rstrip()
    for closer in ("}", '"}', "]}"):
        obj = extract_json_from_output(text + closer)
        if isinstance(obj, dict):
            return obj
    return None


def status() -> dict:
    """{"vllm_up": bool, "models": ["judge", "planner"]}"""
    return _request("GET", "/status", retries=2)


def is_available() -> bool:
    try:
        s = status()
        return bool(s.get("vllm_up")) and {"judge", "planner"} <= set(s.get("models", []))
    except TraceLLMError:
        return False


def _normalize_plan(obj) -> dict:
    if not isinstance(obj, dict) or not isinstance(obj.get("sub_questions"), list):
        raise TraceLLMError("planner output has no 'sub_questions' list")
    sub_questions = []
    for s in obj["sub_questions"]:
        if not isinstance(s, dict):
            continue
        topic = str(s.get("topic") or "").strip()
        details = [str(d).strip() for d in (s.get("details") or []) if str(d).strip()]
        if topic:
            sub_questions.append({"topic": topic, "details": details})
    if not sub_questions:
        raise TraceLLMError("planner returned no usable sub-questions")
    queries = [str(q).strip() for q in (obj.get("search_queries") or []) if str(q).strip()]
    return {"sub_questions": sub_questions, "search_queries": queries}


def decompose(question: str, max_new_tokens: int = 768) -> dict:
    """Planner. Returns {"sub_questions": [{"topic", "details": [...]}], "search_queries": [...]}.

    search_queries is ONE flat list for the whole question (not grouped per sub-question)."""
    for tokens in (max_new_tokens, max_new_tokens * 2):         # a cut-off JSON reply gets one retry with more room
        data = _request("POST", "/decompose", {"question": question, "max_new_tokens": tokens})
        obj = extract_json_from_output(data.get("raw_output", ""))
        if obj is not None:
            return _normalize_plan(obj)
        logger.warning("Planner output was not valid JSON with max_new_tokens=%d (likely cut off)", tokens)
    raise TraceLLMError("planner output was not valid JSON")


def judge(sub_question: str, title: str, abstract: str, max_new_tokens: int = 256, thinking: bool = False) -> dict:
    """Judge. Returns {"relevant": bool, "confidence": float 0-1, "reason": str}."""
    data = _request("POST", "/judge", {
        "sub_question": sub_question, "title": title, "abstract": abstract,
        "max_new_tokens": max_new_tokens, "thinking": thinking,
    })
    verdict = data.get("verdict")
    if not isinstance(verdict, dict):                           # wrapper could not parse it: try the raw text ourselves
        verdict = extract_json_repairing(data.get("raw_output", ""))
    if not isinstance(verdict, dict) or not isinstance(verdict.get("relevant"), bool):
        raise TraceLLMError("judge returned no usable verdict")
    try:
        confidence = min(max(float(verdict.get("confidence", 0.0)), 0.0), 1.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return {"relevant": verdict["relevant"], "confidence": confidence, "reason": str(verdict.get("reason", ""))}
