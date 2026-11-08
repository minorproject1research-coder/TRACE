"""The three LLM judges of Stage 4. Every one FAILS CLOSED: any error means "no conflict", "does not support", "not the same", so a judge
failure can never create a conflict, a support or a merge (handoff report section 11; keep this).

Answers are cached on disk (STAGE4_CACHE, default on, .cache/stage4_judge): a rerun of Stage 4 on the same claims gives the same labels and
costs no LLM calls, which matters because the free Groq quota is the scarce resource. A failed call is never cached, only a parsed reply.
`run_parallel` runs independent judge calls on a few threads (STAGE4_WORKERS, default 4) and returns the results in input order, so the
outcome never depends on which thread finished first.
"""
import hashlib
import json
import logging
import os
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Sequence, TypeVar

from apps.api.services import llm_service
from apps.api.services.llm_service import squeezer_json

logger = logging.getLogger("apps.api.agents.stage4_factcheck")
T = TypeVar("T")


# ------------------------------------------------------------------------------------------------------------ counters + breaker
class JudgeUnavailable(Exception):
    """The judge model is rate limited for good (a daily Groq limit) or was just found to be: the call is not even tried."""


_lock = threading.Lock()
_stats = {"calls": 0, "cache_hits": 0, "failures": 0, "skipped": 0}
_breaker_until = 0.0
BREAKER_SECONDS = 300.0


def stats() -> dict:
    """Counters since the process started (take two snapshots and subtract to count one piece of work)."""
    with _lock:
        return dict(_stats)


def reset_breaker() -> None:
    global _breaker_until
    with _lock:
        _breaker_until = 0.0


def _bump(key: str) -> None:
    with _lock:
        _stats[key] += 1


def _rate_limited_for_good(e: Exception) -> bool:
    """Groq 'all keys rate limited for 179s' / 'gave up after ...s of rate limits': waiting will not help within this run."""
    name = type(e).__name__
    return name == "GroqRateLimitExhausted" or "rate limited for" in str(e) or "of rate limits" in str(e)


# ------------------------------------------------------------------------------------------------------------ cache + parallel
def _cache_on() -> bool:
    return os.getenv("STAGE4_CACHE", "true").strip().lower() not in ("0", "false", "no", "off")


def _cache_dir() -> Path:
    return Path(os.getenv("STAGE4_CACHE_DIR", ".cache/stage4_judge"))


def workers() -> int:
    try:
        return max(1, int(os.getenv("STAGE4_WORKERS", "4")))
    except ValueError:
        return 4


def ask(prompt: str, purpose: str = "stage4_judge") -> dict:
    """squeezer_json with the disk cache. Raises on failure (callers turn that into their fail-closed answer).
    After a rate-limit-for-good failure the model is not asked again for BREAKER_SECONDS (cached answers still work): a sub-question would
    otherwise wait on hundreds of calls that all fail, and every one of them fails closed anyway."""
    global _breaker_until
    path = None
    if _cache_on():
        key = hashlib.sha256(f"{getattr(llm_service, 'MODEL_NAME', '')}|{prompt}".encode("utf-8")).hexdigest()
        path = _cache_dir() / f"{key}.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            _bump("cache_hits")
            return value
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            logger.warning("stage 4 judge cache entry %s unreadable; asking again", key[:12])
    with _lock:
        tripped = time.monotonic() < _breaker_until
    if tripped:
        _bump("skipped")
        raise JudgeUnavailable("the judge model is rate limited; not asked again for a few minutes")
    _bump("calls")
    try:
        value = squeezer_json(prompt, purpose=purpose)
    except Exception as e:
        _bump("failures")
        if _rate_limited_for_good(e):
            with _lock:
                _breaker_until = time.monotonic() + BREAKER_SECONDS
            logger.warning("Stage 4: the judge model is rate limited (%s); judge calls fail closed for the next %.0f s", str(e)[:100], BREAKER_SECONDS)
        raise
    if path is not None and isinstance(value, dict):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(value, f, ensure_ascii=False)
            os.replace(tmp, path)                       # atomic: parallel workers never see half a file
        except OSError as e:
            logger.warning("stage 4 judge cache write failed: %s", e)
    return value


def run_parallel(fn: Callable[..., T], jobs: Sequence[tuple]) -> list[T]:
    """[fn(*job) for job in jobs], on up to STAGE4_WORKERS threads, results in input order."""
    jobs = list(jobs)
    if len(jobs) <= 1 or workers() <= 1:
        return [fn(*j) for j in jobs]
    with ThreadPoolExecutor(max_workers=min(workers(), len(jobs))) as pool:
        return list(pool.map(lambda j: fn(*j), jobs))


# ------------------------------------------------------------------------------------------------------------------ the judges
PROMPT = """You compare two statements from different research sources.

Statement A: {claim}
Evidence from source B: "{quote}"
Source B's claim: {other_claim}

Decide whether the two sources DIRECTLY CONTRADICT each other.
Apply this test: could both statements be true at the same time?
- If yes (different scope, different language, dataset or setting, different metric, or one
  is just more specific), they do NOT conflict.
- Only answer conflicts=true if they assert opposite things about the SAME subject, the same
  property and the same setting.
- Do not stretch wording: related topics or loosely similar terms (e.g. "accuracy" vs "fitness")
  are not the same aspect.
- A hedged statement ("can", "may", "potentially", "often", "in some cases", "usually") does not conflict with a
  statement that something is possible in other cases.
- An aim or intention ("aims to", "is designed to", "is crucial") is not a result, so it does not conflict with
  a measured result that points the other way.
- Different models, datasets, methods or settings are not the same setting.

Return ONLY JSON: {{"same_aspect": true, "conflicts": true, "confidence": 0.0, "reason": "one sentence"}}
(use true/false for the first two fields and a number from 0 to 1 for confidence)"""


CONFIRM_PROMPT = """Statement A: {claim}
Evidence from another source: "{quote}"

A second reader says these two DIRECTLY CONTRADICT each other. Try to prove them wrong.
Can both be true at the same time under any reasonable reading? Check each of these:
- hedging (can, may, potentially, often, usually, in some cases) on either side
- an aim or intention on one side and a measured result on the other
- different models, datasets, methods, metrics, scale or conditions
- one side is more specific, or only partly overlaps the other
If any of them makes both statements possible together, answer both_can_be_true=true.
Answer false only if the evidence plainly asserts the opposite of A about the same thing in the same setting.

Return ONLY JSON: {{"both_can_be_true": true, "reason": "one sentence"}}"""


def judge_conflict(claim: str, quote: str, other_claim: str) -> dict:
    """A conflict needs TWO yeses: the first reading says "conflicts", and a second reading that tries to reconcile the statements fails.
    A single lenient answer from one call (the first real run produced two false conflicts that way) cannot create a conflict."""
    try:
        v = ask(PROMPT.format(claim=claim, quote=quote, other_claim=other_claim), "stage4_conflict")
        out = {
            "same_aspect": bool(v.get("same_aspect")),
            "conflicts": bool(v.get("conflicts")),
            "confidence": float(v.get("confidence", 0.0)),
            "reason": str(v.get("reason", "")),
        }
        if out["conflicts"] and out["same_aspect"]:
            c = ask(CONFIRM_PROMPT.format(claim=claim, quote=quote), "stage4_conflict")
            if bool(c.get("both_can_be_true", True)):          # a missing field counts as "can be reconciled"
                out["conflicts"] = False
                out["reason"] = "not confirmed: " + str(c.get("reason", ""))
        return out
    except Exception as e:
        logger.warning("Conflict judge failed: %s", e)
        return {"same_aspect": False, "conflicts": False, "confidence": 0.0,
                "reason": f"judge failed: {e}"}


SUPPORT_PROMPT = """Quote from a research source: "{quote}"
Claim: "{claim}"

Does the quote support the claim?
- Yes only if everything the claim asserts is stated or clearly implied by the quote.
- No if the claim adds a fact, number, cause, comparison or detail that the quote does not contain.
- The quote comes from a paper about the claim's topic, so it need not repeat the topic's name.
- Ignore formatting noise in the quote (figure labels, stray symbols, broken spacing).

Return ONLY JSON: {{"supports": true, "confidence": 0.0, "reason": "one sentence"}}
(use true or false for supports, and a number from 0 to 1 for confidence)"""


def judge_support(claim: str, quote: str) -> dict:
    try:
        v = ask(SUPPORT_PROMPT.format(claim=claim, quote=quote), "stage4_support")
        return {
            "supports": bool(v.get("supports")),
            "confidence": float(v.get("confidence", 0.0)),
            "reason": str(v.get("reason", "")),
        }
    except Exception as e:
        logger.warning("Support judge failed: %s", e)
        return {"supports": False, "confidence": 0.0, "reason": f"judge failed: {e}"}


NEAR_PROMPT = """Two claims from different research sources.

Claim 1: "{a}"
Claim 2: "{b}"
Evidence behind claim 2: "{quote}"

Claim 1 has one main point. Does source 2 make that same main point, in other words, more generally or more specifically?
First write the point both make, in one short sentence ("shared_point"). If there is no single point that BOTH claims make, write "none".
Then answer near=true only if all of these hold:
- the shared point is a specific property of the same subject (not only "both are about MoE" or "both are about training")
- the two claims point the same way
- the main point of claim 1 is stated by claim 2 or its evidence, not merely something related to it
Answer near=false, shared_point "none", when for example:
- they are about different properties (efficiency vs interpretability vs training stability vs cost vs accuracy vs challenges)
- claim 2 is a cause, example or consequence of something else, not the point of claim 1
- the main point of claim 1 is a number, cause, comparison or condition that source 2 does not give

Return ONLY JSON: {{"shared_point": "...", "near": true, "reason": "one sentence"}}
(use true or false for near)"""


def judge_near_match(claim: str, other_claim: str, other_quote: str) -> bool:
    """Fails closed like the other judges: any error means "not a near match"."""
    try:
        v = ask(NEAR_PROMPT.format(a=claim, b=other_claim, quote=other_quote), "stage4_near")
        shared = str(v.get("shared_point", "")).strip().lower().strip(".\"' ")
        return bool(v.get("near")) and shared not in ("", "none", "n/a")      # a yes without a named shared point does not count
    except Exception as e:
        logger.warning("Near-match judge failed: %s", e)
        return False


SAME_PROMPT = """Two claims from different research sources.

Claim 1: "{a}"
Claim 2: "{b}"

Do they make the SAME specific assertion? Answer yes only if someone who believes one claim
would necessarily believe the other.
Answer no if:
- one gives a mechanism, cause, number, condition or scope that the other lacks
- one is a general statement ("it is faster") and the other a specific one
- they cover different aspects (speed vs memory vs cost vs challenges)

Return ONLY JSON: {{"same": true, "reason": "one sentence"}}
(use true or false for same)"""


def judge_same_claim(a: str, b: str) -> bool:
    try:
        v = ask(SAME_PROMPT.format(a=a, b=b), "stage4_merge")
        return bool(v.get("same"))
    except Exception as e:
        logger.warning("Same-claim judge failed: %s", e)
        return False    # on failure do not merge
