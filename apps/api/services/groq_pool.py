# apps/api/services/groq_pool.py
"""One place for every Groq chat call: several API keys, rate-limit aware retries.

Keys come from GROQ_API_KEYS (comma-separated) and/or GROQ_API_KEY. Calls are spread over the keys round-robin; when a
key answers 429 it is parked for the time Groq asks for (Retry-After) and the call goes to the next key at once. The SDK's
own blind retries are switched off (max_retries=0) so the wait is not spent twice.

IMPORTANT: Groq enforces rate limits per ORGANIZATION, not per API key. Several keys from the same Groq account share one
limit and add nothing; the keys must belong to different organizations (different Groq accounts) to add capacity. Check
Groq's terms before creating accounts to get around a free-tier limit.
"""
import itertools
import json
import logging
import os
import threading
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import groq
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

logger = logging.getLogger("apps.api.services.groq_pool")

DEFAULT_COOLDOWN_SECONDS = 10.0         # when a 429 carries no Retry-After
MAX_WAIT_SECONDS = float(os.getenv("GROQ_MAX_WAIT_SECONDS", "120"))   # longer than this = the limit is exhausted (e.g. daily)
MAX_ATTEMPTS = int(os.getenv("GROQ_MAX_ATTEMPTS", "8"))              # real API calls per chat() (waiting for a parked key does not count)
CALL_TIME_BUDGET_SECONDS = float(os.getenv("GROQ_CALL_TIME_BUDGET_SECONDS", "300"))   # total time one chat() may spend waiting and retrying


class GroqRateLimitExhausted(Exception):
    """Every key is rate limited for longer than MAX_WAIT_SECONDS (or the attempts ran out)."""


# ------------------------------------------------------------------------------------------------------------ token meter
USAGE_LOG = os.getenv("GROQ_USAGE_LOG", "logs/groq_usage.jsonl")      # one JSON line per call; "off" disables the file (the counters stay)


class UsageMeter:
    """Counts what every Groq call costs: tokens (prompt, completion, of which reasoning), calls and 429s, per purpose (digest, stage4_judge ...)
    and per key, in memory (for a per-run figure) and in a log file (for "how much did I use today": scripts/groq_usage.py).
    The limits themselves come from Groq's response headers (x-ratelimit-*): requests per day and tokens per minute per key.
    Groq does not report the daily token limit in headers; the daily total here is what THIS project sent."""

    def __init__(self):
        self._lock = threading.Lock()
        self.totals: Counter = Counter()
        self.by_purpose: dict[str, Counter] = defaultdict(Counter)
        self.by_key: dict[str, Counter] = defaultdict(Counter)
        self.limits: dict[str, dict] = {}                 # last seen x-ratelimit-* per key (last 4 characters)

    def record(self, key: str, purpose: str, model: str, usage, headers) -> None:
        k = key[-4:]
        prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion = int(getattr(usage, "completion_tokens", 0) or 0)
        details = getattr(usage, "completion_tokens_details", None)
        reasoning = int(getattr(details, "reasoning_tokens", 0) or 0)
        total = int(getattr(usage, "total_tokens", 0) or (prompt + completion))
        lim = {}
        for name in ("limit-requests", "remaining-requests", "limit-tokens", "remaining-tokens", "reset-requests", "reset-tokens"):
            v = (headers or {}).get(f"x-ratelimit-{name}") if headers is not None else None
            if v is not None:
                lim[name] = v
        with self._lock:
            for c in (self.totals, self.by_purpose[purpose], self.by_key[k]):
                c["calls"] += 1
                c["prompt"] += prompt
                c["completion"] += completion
                c["reasoning"] += reasoning
                c["total"] += total
            if lim:
                self.limits[k] = {**lim, "at": time.time()}
        self._append({"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "key": k, "purpose": purpose, "model": model, "prompt": prompt,
                      "completion": completion, "reasoning": reasoning, "total": total, **{f"rl_{n.replace('-', '_')}": v for n, v in lim.items()}})

    def rate_limited(self, key: str, purpose: str, seconds: float) -> None:
        k = key[-4:]
        with self._lock:
            for c in (self.totals, self.by_purpose[purpose], self.by_key[k]):
                c["rate_limited"] += 1
                c["parked_seconds"] += int(round(seconds))
        self._append({"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "key": k, "purpose": purpose, "event": "429", "parked_seconds": round(seconds)})

    def _append(self, row: dict) -> None:
        if USAGE_LOG.lower() == "off":
            return
        try:
            path = Path(USAGE_LOG)
            path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock, path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")
        except (OSError, ValueError):
            pass                                           # counting must never break a call

    def snapshot(self) -> dict:
        with self._lock:
            return {"totals": Counter(self.totals), "by_purpose": {p: Counter(c) for p, c in self.by_purpose.items()},
                    "by_key": {k: Counter(c) for k, c in self.by_key.items()}}

    def since(self, snap: dict) -> dict:
        """What was used after `snap` (a snapshot taken earlier): {"totals": {...}, "by_purpose": {...}, "by_key": {...}}."""
        now = self.snapshot()
        diff = lambda a, b: {k: a[k] - b.get(k, 0) for k in a if a[k] - b.get(k, 0)}          # noqa: E731
        return {"totals": diff(now["totals"], snap["totals"]),
                "by_purpose": {p: d for p, c in now["by_purpose"].items() if (d := diff(c, snap["by_purpose"].get(p, {})))},
                "by_key": {k: d for k, c in now["by_key"].items() if (d := diff(c, snap["by_key"].get(k, {})))}}


meter = UsageMeter()


def usage_text(used: dict) -> str:
    """One readable line for a log: 'Groq usage: 412,300 tokens in 96 calls (digest 301,000, digest_loop2 90,500 ...), 14 rate limits'."""
    t = used.get("totals", {})
    parts = ", ".join(f"{p} {c.get('total', 0):,}" for p, c in sorted(used.get("by_purpose", {}).items(), key=lambda kv: -kv[1].get("total", 0)))
    return (f"Groq usage: {t.get('total', 0):,} tokens ({t.get('prompt', 0):,} prompt + {t.get('completion', 0):,} completion, of which {t.get('reasoning', 0):,} reasoning) "
            f"in {t.get('calls', 0)} calls, {t.get('rate_limited', 0)} rate limits" + (f" [{parts}]" if parts else ""))


def load_keys() -> list[str]:
    raw = f"{os.getenv('GROQ_API_KEYS', '')},{os.getenv('GROQ_API_KEY', '')}"
    return list(dict.fromkeys(k.strip() for k in raw.split(",") if k.strip()))


def _retry_after_seconds(error: Exception) -> float | None:
    headers = getattr(getattr(error, "response", None), "headers", None) or {}
    value = headers.get("retry-after")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


class GroqPool:
    def __init__(self, keys: list[str]):
        if not keys:
            raise ValueError("no Groq API key: set GROQ_API_KEY or GROQ_API_KEYS")
        self._keys = keys
        self._clients = {k: Groq(api_key=k, max_retries=0) for k in keys}
        self._cycle = itertools.cycle(keys)
        self._parked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._keys)

    def _acquire(self) -> tuple[str | None, float]:
        """(key, 0) for the next usable key round-robin, or (None, seconds until one is usable)."""
        with self._lock:
            now = time.time()
            for _ in range(len(self._keys)):
                key = next(self._cycle)
                if now >= self._parked_until.get(key, 0.0):
                    return key, 0.0
            return None, max(0.0, min(self._parked_until.get(k, 0.0) for k in self._keys) - now)

    def _park(self, key: str, seconds: float) -> None:
        with self._lock:
            self._parked_until[key] = max(self._parked_until.get(key, 0.0), time.time() + seconds)

    def chat(self, messages: list[dict], model: str, temperature: float = 0.1, purpose: str = "other", **kwargs):
        """chat.completions.create with key rotation. Returns the SDK response.

        A 429 only parks its key and the call goes on (to another key, or after the Retry-After): rate limits are NOT counted against
        MAX_ATTEMPTS, because with every key near its tokens-per-minute limit a call can be refused many times in a row and still be
        fine a few seconds later (a digest was lost that way after 8 refusals). Only real errors (connection, 5xx) use up
        MAX_ATTEMPTS. The whole call is bounded by CALL_TIME_BUDGET_SECONDS, and GroqRateLimitExhausted is raised at once when every
        key is limited for longer than MAX_WAIT_SECONDS (a daily limit)."""
        last: Exception | None = None
        errors = 0
        deadline = time.time() + CALL_TIME_BUDGET_SECONDS
        while errors < MAX_ATTEMPTS:
            if time.time() > deadline:
                raise GroqRateLimitExhausted(f"gave up after {CALL_TIME_BUDGET_SECONDS:.0f}s of rate limits") from last
            key, wait = self._acquire()
            if key is None:
                if wait > MAX_WAIT_SECONDS or time.time() + wait > deadline:
                    raise GroqRateLimitExhausted(f"all {len(self._keys)} Groq key(s) are rate limited for {wait:.0f}s")
                time.sleep(max(wait, 0.2))
                continue
            try:
                raw = self._clients[key].chat.completions.with_raw_response.create(
                    model=model, messages=messages, temperature=temperature, **kwargs)
                response = raw.parse()                       # the same object create() returns; the raw response also carries the rate-limit headers
                meter.record(key, purpose, model, getattr(response, "usage", None), getattr(raw, "headers", None))
                return response
            except groq.RateLimitError as e:
                seconds = _retry_after_seconds(e) or DEFAULT_COOLDOWN_SECONDS
                self._park(key, seconds)
                meter.rate_limited(key, purpose, seconds)
                last = e
                logger.info("Groq key ...%s rate limited, parked %.0fs (%d key(s) in the pool)", key[-4:], seconds, len(self._keys))
            except (groq.APIConnectionError, groq.InternalServerError) as e:
                last = e
                errors += 1
                time.sleep(min(2 ** (errors - 1), 15))
        raise last if last else GroqRateLimitExhausted("no attempt was made")


_pool: GroqPool | None = None
_pool_lock = threading.Lock()


def get_pool() -> GroqPool:
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = GroqPool(load_keys())
        return _pool


def chat(messages: list[dict], model: str, temperature: float = 0.1, purpose: str = "other", **kwargs):
    return get_pool().chat(messages, model, temperature, purpose=purpose, **kwargs)


def key_count() -> int:
    return len(load_keys())
