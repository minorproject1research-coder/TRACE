"""The writer of Stage 5: one sentence per job (1-3 claims of one tier), written by the LLM, checked by Python, replaced by a deterministic
sentence when the checks fail twice. The LLM never decides what may be said and never writes a citation; it phrases and names the claim ids.

How `write_section` works (read with prompts.py and settings.py):
  1. The jobs of a section are cut into calls whose prompt stays under STAGE5_MAX_PROMPT_TOKENS (about 4 characters per token).
  2. Every call asks for strict JSON {"sentences":[{"job_id","text","claim_ids"}]} through groq_pool.chat (reasoning_effort low).
     A validated reply is cached on disk (STAGE5_CACHE, .cache/stage5) under the FIRST-attempt prompt; a hit is validated again, a failure
     is never cached.
  3. Every returned sentence goes through `check(text, claim_ids, job) -> [reason]` (default: validators.check_sentence, then the NLI
     grounding in grounding.entails). A job that is missing from the reply, malformed JSON and a failed check all count as a failed attempt.
  4. Failed jobs are asked again ONCE (STAGE5_RETRIES) with the Python-written reasons; still failing -> `hedging.fallback_sentence(job)`.
  5. An LLM error (network, a rate limit that cannot be waited out) gives the fallback for the jobs of that call only, without a retry.
     HTTP 413 (request too large) splits the call in two and asks again; that is not the retry.
  Nothing in here raises: the worst case is that every sentence is a fallback sentence.

Rate limits follow the Stage 4 pattern (`RateGuard`): a pool-wide limit of at most STAGE5_RATE_WAIT_MAX seconds is waited out; a longer one
trips a breaker so the next calls are not even sent for STAGE5_BREAKER_SECONDS (they fall back at once).

The LLM is injectable: `llm(messages, response_format, purpose)` returns the parsed JSON dict, or `(dict, usage)` with usage a dict that may
hold prompt_tokens / completion_tokens / total_tokens. Tests pass a fake; the default is `default_llm`.
"""
import contextvars
import hashlib
import json
import logging
import os
import re
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from apps.api.agents.stage5_report import prompts, settings
from apps.api.agents.stage5_report.schema import (ORIGIN_FALLBACK, ORIGIN_LLM, TIER_PARTLY, TIER_SINGLE, TIER_SUPPORTED, Sentence)

logger = logging.getLogger("apps.api.agents.stage5_report")

PURPOSE_WRITE = "stage5_write"          # meter purposes (groq_pool.UsageMeter)
PURPOSE_SUMMARY = "stage5_summary"
PURPOSE_CHECK = "stage5_check"          # used by the NLI grounding of agent CHECK; listed here so the three names live in one place


class LLMUnavailable(Exception):
    """The model is rate limited for good (breaker tripped): the call is not made."""


class TooLarge(Exception):
    """HTTP 413: the request was too large for the model's limit."""


class MalformedReply(Exception):
    """The reply was not a JSON object (or not JSON at all)."""


class BadJson(Exception):
    """Groq HTTP 400 `json_validate_failed`: the reply was cut off by max_completion_tokens ("max completion tokens reached before generating a
    valid document": the reasoning tokens count too) or was not valid JSON for the schema. Smaller calls usually work, so it is not a dead end."""


# ------------------------------------------------------------------------------------------------------------ stats
_STAT_KEYS = ("jobs", "calls", "prompt_tokens", "completion_tokens", "total_tokens", "retried", "fallback", "dropped", "cache_hits",
              "splits", "malformed", "llm_errors", "skipped", "rate_waits", "llm_sentences", "extractive")


def new_stats() -> dict:
    return {k: 0 for k in _STAT_KEYS}


def merge_stats(*parts) -> dict:
    out = new_stats()
    for p in parts:
        for k, v in (p or {}).items():
            if isinstance(v, (int, float)):
                out[k] = out.get(k, 0) + v
    return out


# ------------------------------------------------------------------------------------------------------------ rate limits (Stage 4 pattern)
def rate_wait_seconds(e: Exception):
    """'all 7 Groq key(s) are rate limited for 124s' -> 124.0 (worth waiting for); None for anything else."""
    m = re.search(r"rate limited for (\d+)s", str(e))
    return float(m.group(1)) if m else None


def rate_limited_for_good(e: Exception) -> bool:
    name = type(e).__name__
    return name == "GroqRateLimitExhausted" or "rate limited for" in str(e) or "of rate limits" in str(e)


def is_too_large(e: Exception) -> bool:
    if getattr(e, "status_code", None) == 413:
        return True
    return bool(re.search(r"\b413\b|request too large|request_too_large|reduce your message size", str(e), re.I))


def is_bad_json(e: Exception) -> bool:
    """A 400 whose code is json_validate_failed ('Failed to generate JSON' = cut off by the token cap, 'Failed to validate JSON' = not valid JSON)."""
    body = getattr(e, "body", None)
    if isinstance(body, dict):
        err = body.get("error") if isinstance(body.get("error"), dict) else body
        if isinstance(err, dict) and err.get("code") == "json_validate_failed":
            return True
    return "json_validate_failed" in str(e)


class RateGuard:
    """Waits out a pool-wide rate limit and keeps the breaker. One guard is shared by all Stage 5 calls of the process (`default_rate`)."""

    def __init__(self, sleep=None):
        self._lock = threading.Lock()
        self._until = 0.0
        self._sleep = sleep

    def reset(self) -> None:
        with self._lock:
            self._until = 0.0

    def tripped(self) -> bool:
        with self._lock:
            return time.monotonic() < self._until

    def call(self, fn, on_wait=None):
        if self.tripped():
            raise LLMUnavailable("the writer model is rate limited; not asked again for a few minutes")
        attempt = 0
        while True:
            try:
                return fn()
            except Exception as e:
                if isinstance(e, (MalformedReply, json.JSONDecodeError, TooLarge, BadJson)) or is_too_large(e) or is_bad_json(e):
                    raise
                wait = rate_wait_seconds(e)
                if wait is not None and wait <= settings.rate_wait_max() and attempt < settings.rate_retries():
                    attempt += 1
                    if on_wait:
                        on_wait()
                    logger.info("Stage 5: every Groq key is parked for %.0f s; waiting (%d of %d)", wait, attempt, settings.rate_retries())
                    (self._sleep or time.sleep)(wait + 1.0)
                    continue
                if rate_limited_for_good(e):
                    with self._lock:
                        self._until = time.monotonic() + settings.breaker_seconds()
                    logger.warning("Stage 5: the writer model is rate limited (%s); not asked again for %.0f s", str(e)[:100], settings.breaker_seconds())
                    raise LLMUnavailable(str(e)) from e
                raise


default_rate = RateGuard()


# ------------------------------------------------------------------------------------------------------------ the LLM
def default_llm(messages, response_format, purpose):
    """groq_pool.chat with strict json_schema, reasoning_effort low and a max_completion_tokens (the pool passes these kwargs straight to the
    SDK). Returns (parsed dict, usage dict). A reply that is not JSON raises json.JSONDecodeError."""
    from apps.api.services import groq_pool, llm_service
    resp = groq_pool.chat(messages=messages, model=settings.model(), temperature=settings.temperature(), purpose=purpose,
                          response_format=response_format, max_completion_tokens=settings.max_output_tokens(),
                          reasoning_effort=settings.reasoning_effort())
    usage = getattr(resp, "usage", None)
    usage_dict = {"prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0), "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
                  "total_tokens": int(getattr(usage, "total_tokens", 0) or 0)}
    return llm_service._parse_json(resp.choices[0].message.content or ""), usage_dict


def call_llm(llm, messages, response_format, purpose, *, rate=None, stats=None) -> dict:
    """One LLM call through the rate guard, counted in `stats`. Raises TooLarge, MalformedReply, LLMUnavailable or the LLM's own error."""
    llm = llm or default_llm
    rate = rate or default_rate
    stats = stats if stats is not None else new_stats()
    stats["calls"] += 1

    def on_wait():
        stats["rate_waits"] += 1
    try:
        raw = rate.call(lambda: llm(messages, response_format, purpose), on_wait=on_wait)
    except LLMUnavailable:
        stats["skipped"] += 1
        raise
    except json.JSONDecodeError as e:
        raise MalformedReply(f"not valid JSON: {e}") from e
    except (TooLarge, MalformedReply, BadJson):
        raise
    except Exception as e:
        if is_too_large(e):
            raise TooLarge(str(e)) from e
        if is_bad_json(e):
            raise BadJson(str(e)) from e
        raise
    data, usage = (raw[0], raw[1]) if isinstance(raw, tuple) and len(raw) == 2 else (raw, None)
    if isinstance(usage, dict):
        p, c = int(usage.get("prompt_tokens", 0) or 0), int(usage.get("completion_tokens", 0) or 0)
        stats["prompt_tokens"] += p
        stats["completion_tokens"] += c
        stats["total_tokens"] += int(usage.get("total_tokens", 0) or (p + c))
    if not isinstance(data, dict):
        raise MalformedReply("the reply was not a JSON object")
    return data


# ------------------------------------------------------------------------------------------------------------ cache
class DiskCache:
    """One file per key, atomic write (parallel workers never see half a file). Only validated replies are put here (the callers decide)."""

    def __init__(self, directory=None):
        self.directory = Path(directory or settings.cache_dir())

    def get(self, key: str):
        path = self.directory / f"{key}.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            logger.warning("stage 5 cache entry %s unreadable; asking again", key[:12])
            return None

    def put(self, key: str, value) -> None:
        target = self.directory / f"{key}.json"
        tmp = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.directory, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(value, f, ensure_ascii=False)
            for attempt in range(5):
                try:
                    os.replace(tmp, target)
                    tmp = None
                    return
                except PermissionError:             # Windows: another thread is replacing the same key right now; the content is the same
                    if target.exists() and attempt >= 1:
                        return
                    time.sleep(0.02 * (attempt + 1))
            os.replace(tmp, target)
            tmp = None
        except OSError as e:
            logger.warning("stage 5 cache write failed: %s", e)
        finally:
            if tmp is not None:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass


def resolve_cache(cache):
    """None = the default disk cache when STAGE5_CACHE is on; False = no cache; anything else with get/put is used as it is."""
    if cache is None:
        return DiskCache() if settings.cache_enabled() else None
    return cache or None


def cache_key(messages) -> str:
    """sha256 of model, template version, reasoning effort, max output tokens and the rendered prompt."""
    raw = f"{settings.model()}|{settings.template_version()}|{settings.reasoning_effort()}|{settings.max_output_tokens()}|{prompts.dumps(messages)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def safe_progress(progress, step: str, message: str, **data) -> None:
    """A progress report never raises out of the writer."""
    if progress is None:
        return
    try:
        progress(step, message, **data)
    except Exception:
        logger.debug("stage 5 progress callback failed", exc_info=True)


# ------------------------------------------------------------------------------------------------------------ default checks and fallback
def _evidence_texts(job, claim_ids) -> list:
    """Premises for the grounding check: the claim text and the quotes (and the related wording of a partly claim) of the claims the sentence names."""
    wanted = set(claim_ids or [])
    texts = []
    for c in job.claims:
        if wanted and c.claim_id not in wanted:
            continue
        texts.append(c.text)
        for e in getattr(c, "evidence", []):
            if getattr(e, "relation", "supports") in ("supports", "near_match"):
                if getattr(e, "near_claim", None):
                    texts.append(e.near_claim)
                if getattr(e, "quote", None):
                    texts.append(e.quote)
    return [t for t in texts if t]


def default_check(text: str, claim_ids: list, job) -> list:
    """validators.check_sentence (pure Python), then grounding.entails (NLI + judge, fail closed). Reasons, empty = pass. Imports are lazy, so
    nothing heavy loads before the first check; a missing module fails closed."""
    try:
        from apps.api.agents.stage5_report import validators
        reasons = list(validators.check_sentence(text, claim_ids, job) or [])
        if reasons:
            return reasons
        from apps.api.agents.stage5_report import grounding
        ok, detail = grounding.entails(text, _evidence_texts(job, claim_ids))
        if not ok:
            why = detail.get("reason") if isinstance(detail, dict) else None
            return [why or "the sentence is not entailed by the quotes of its claims; say only what the claims and quotes say"]
        return []
    except Exception as e:
        logger.warning("Stage 5 check failed to run: %s", e)
        return [f"the check could not run ({type(e).__name__}); the sentence cannot be accepted"]


def default_tier_rules():
    try:
        from apps.api.agents.stage5_report import hedging
        return hedging.rules() if hasattr(hedging, "rules") else getattr(hedging, "TIER_RULES", None)
    except Exception:
        return None


def default_fallback(job):
    from apps.api.agents.stage5_report import hedging
    return hedging.fallback_sentence(job)


_OPENERS = {TIER_SUPPORTED: "Two sources report that ", TIER_PARTLY: "One source reports that ", TIER_SINGLE: "One study reports that "}


def _last_resort(job) -> str:
    """Used only when hedging.fallback_sentence is missing or raises: the claims' own wording behind the tier's opener, nothing added."""
    parts = [" ".join(str(c.text).split()).rstrip(".") for c in job.claims if getattr(c, "text", "")]
    if not parts:
        return ""
    return _OPENERS.get(job.tier, "One study reports that ") + "; ".join(parts) + "."


def _unpack_fallback(out, job):
    ids = [c.claim_id for c in job.claims]
    if isinstance(out, str):
        return out, ids
    if isinstance(out, dict):
        return out.get("text", ""), list(out.get("claim_ids") or ids)
    return getattr(out, "text", ""), list(getattr(out, "claim_ids", None) or ids)


# ------------------------------------------------------------------------------------------------------------ one section
class _Ctx:
    def __init__(self, title, llm, check, cache, progress, rate, tier_rules, fallback, retries, stats):
        self.title, self.llm, self.check, self.cache, self.progress, self.rate = title, llm, check, cache, progress, rate
        self.tier_rules, self.fallback, self.retries, self.stats = tier_rules, fallback, retries, stats


def split_jobs(section_title: str, jobs, tier_rules=None, max_tokens=None) -> list:
    """Cuts the jobs (in order) into calls whose estimated prompt stays under the cap. A single job bigger than the cap goes alone."""
    cap = max_tokens or settings.max_prompt_tokens()
    groups, current = [], []
    for job in jobs:
        candidate = current + [job]
        if current and prompts.estimate_messages_tokens(prompts.write_messages(section_title, candidate, tier_rules)) > cap:
            groups.append(current)
            current = [job]
        else:
            current = candidate
    if current:
        groups.append(current)
    return groups


def _clean(text) -> str:
    return " ".join(str(text).split())


def _validate(job, entry, ctx) -> list:
    """Reasons a returned entry is not acceptable (empty = accepted). The basic shape and the 'ids belong to this job' rule are checked here;
    everything else is ctx.check's."""
    if not isinstance(entry, dict):
        return ["no sentence was returned for this job"]
    text, ids = entry.get("text"), entry.get("claim_ids")
    if not isinstance(text, str) or not text.strip():
        return ["the sentence is empty"]
    if not isinstance(ids, list) or not ids or not all(isinstance(i, str) for i in ids):
        return ["claim_ids must list at least one claim id of this job"]
    allowed = {c.claim_id for c in job.claims}
    own = [i for i in dict.fromkeys(ids) if i in allowed]
    if not own:
        return [f"claim id(s) {', '.join(ids)} do not belong to this job; use only the claim ids listed for this job"]
    # A model that answers several jobs in one call sometimes also lists an id of a neighbouring job (first live run: 9 of 15 rejections). The sentence
    # is still checked below against its OWN claims only (numbers, names, hedge, entailment), and the foreign ids are dropped here, so they can never
    # become citations: nothing is gained by throwing the sentence away.
    ids = own
    entry["claim_ids"] = own
    try:
        reasons = ctx.check(_clean(text), list(dict.fromkeys(ids)), job)
    except Exception as e:
        logger.warning("Stage 5 check raised: %s", e)
        return [f"the check could not run ({type(e).__name__})"]
    return [str(r) for r in (reasons or [])]


def _parse_reply(data: dict, jobs):
    """{job_id: entry} for the jobs of this call (the first entry per job; foreign job ids are ignored), or None when 'sentences' is not a list."""
    items = data.get("sentences")
    if not isinstance(items, list):
        return None
    wanted = {j.job_id for j in jobs}
    out = {}
    for it in items:
        if isinstance(it, dict) and it.get("job_id") in wanted and it["job_id"] not in out:
            out[it["job_id"]] = it
    return out


def _ask_jobs(jobs, build, ctx):
    """One LLM call for `jobs` (a 413 splits it in two and asks both halves; that is not a retry). Returns (replies {job_id: entry},
    errors {job_id: (kind, reason)}) with kind "retry" (a retry may help) or "fatal" (go straight to the fallback)."""
    messages = build(jobs)
    try:
        data = call_llm(ctx.llm, messages, prompts.section_schema(jobs), PURPOSE_WRITE, rate=ctx.rate, stats=ctx.stats)
    except TooLarge as e:
        if len(jobs) > 1:
            ctx.stats["splits"] += 1
            mid = len(jobs) // 2
            r1, e1 = _ask_jobs(jobs[:mid], build, ctx)
            r2, e2 = _ask_jobs(jobs[mid:], build, ctx)
            return {**r1, **r2}, {**e1, **e2}
        ctx.stats["llm_errors"] += 1
        return {}, {jobs[0].job_id: ("fatal", f"the request was too large ({str(e)[:80]})")}
    except BadJson as e:               # a 400 json_validate_failed (usually the token cap): the same call would fail again, a smaller one usually works
        ctx.stats["malformed"] += 1
        logger.warning("Stage 5: Groq refused the JSON of a call with %d job(s) (%s)", len(jobs), str(e)[:300])
        if len(jobs) > 1:
            ctx.stats["splits"] += 1
            mid = len(jobs) // 2
            r1, e1 = _ask_jobs(jobs[:mid], build, ctx)
            r2, e2 = _ask_jobs(jobs[mid:], build, ctx)
            return {**r1, **r2}, {**e1, **e2}
        return {}, {jobs[0].job_id: ("retry", "the answer was cut off or was not valid JSON; write a shorter sentence and return the JSON object exactly as specified")}
    except MalformedReply as e:
        ctx.stats["malformed"] += 1
        return {}, {j.job_id: ("retry", f"the reply was not usable JSON ({str(e)[:80]}); return the JSON object exactly as specified") for j in jobs}
    except LLMUnavailable as e:
        return {}, {j.job_id: ("fatal", f"the model was not available ({str(e)[:80]})") for j in jobs}
    except Exception as e:
        ctx.stats["llm_errors"] += 1
        logger.warning("Stage 5 LLM call failed (%s): %s", type(e).__name__, str(e)[:200])
        return {}, {j.job_id: ("fatal", f"the model call failed ({type(e).__name__})") for j in jobs}
    replies = _parse_reply(data, jobs)
    if replies is None:
        ctx.stats["malformed"] += 1
        return {}, {j.job_id: ("retry", "the reply had no 'sentences' list; return the JSON object exactly as specified") for j in jobs}
    return replies, {}


def _fallback_sentence(job, ctx, reasons, attempts) -> Sentence:
    try:
        text, ids = _unpack_fallback((ctx.fallback or default_fallback)(job), job)
        if not str(text).strip():
            raise ValueError("empty fallback sentence")
    except Exception as e:
        logger.warning("Stage 5 fallback_sentence failed (%s); using the last-resort wording", e)
        text, ids = _last_resort(job), [c.claim_id for c in job.claims]
    ctx.stats["fallback"] += 1
    logger.info("Stage 5: fallback sentence for job %s (%s, %d claim(s), %d attempt(s)); reasons: %s", job.job_id, job.tier, len(job.claims), attempts,
                " | ".join(str(r)[:200] for r in list(reasons)[:6]) or "none")
    return Sentence(text=_clean(text), claim_ids=list(ids), job_id=job.job_id, tier=job.tier, origin=ORIGIN_FALLBACK, attempts=attempts, reasons=list(reasons))


def _run_group(group, ctx) -> dict:
    """{job_id: Sentence} for one call's worth of jobs."""
    title, stats = ctx.title, ctx.stats
    first = prompts.write_messages(title, group, ctx.tier_rules)
    key = cache_key(first)
    if ctx.cache is not None:
        try:
            stored = ctx.cache.get(key)
        except Exception:
            stored = None
        hit = _parse_reply(stored, group) if isinstance(stored, dict) else None
        if hit is not None and all(not _validate(j, hit.get(j.job_id), ctx) for j in group):      # re-validated: a changed validator is never bypassed
            stats["cache_hits"] += len(group)
            return {j.job_id: Sentence(text=_clean(hit[j.job_id]["text"]), claim_ids=list(dict.fromkeys(hit[j.job_id]["claim_ids"])), job_id=j.job_id,
                                       tier=j.tier, origin=ORIGIN_LLM, attempts=1) for j in group}
    pending, good, log, attempts, prev = list(group), {}, {j.job_id: [] for j in group}, {}, {}
    for attempt in range(1, ctx.retries + 2):
        if not pending:
            break
        if attempt == 1:
            def build(js):
                return prompts.write_messages(title, js, ctx.tier_rules)
        else:
            stats["retried"] += len(pending)

            def build(js):
                return prompts.retry_messages(title, js, prev, ctx.tier_rules)
        replies, errors = _ask_jobs(pending, build, ctx)
        nxt = []
        for job in pending:
            attempts[job.job_id] = attempt
            if job.job_id in errors:
                kind, reason = errors[job.job_id]
                log[job.job_id].append(reason)
                prev[job.job_id] = {"text": "", "reasons": [reason]}
                if kind == "retry":
                    nxt.append(job)
                continue
            entry = replies.get(job.job_id)
            reasons = _validate(job, entry, ctx)
            if not reasons:
                good[job.job_id] = entry
                continue
            log[job.job_id].extend(reasons)
            logger.info("Stage 5: job %s (%s) attempt %d rejected: %s | sentence: %s", job.job_id, job.tier, attempt,
                        " | ".join(r[:200] for r in reasons[:6]), _clean(entry.get("text", ""))[:300] if isinstance(entry, dict) else "")
            prev[job.job_id] = {"text": entry.get("text", "") if isinstance(entry, dict) else "", "reasons": reasons}
            nxt.append(job)
        pending = nxt
    out = {}
    for job in group:
        if job.job_id in good:
            e = good[job.job_id]
            stats["llm_sentences"] += 1
            out[job.job_id] = Sentence(text=_clean(e["text"]), claim_ids=list(dict.fromkeys(e["claim_ids"])), job_id=job.job_id, tier=job.tier,
                                       origin=ORIGIN_LLM, attempts=attempts.get(job.job_id, 1), reasons=log[job.job_id])
        else:
            out[job.job_id] = _fallback_sentence(job, ctx, log[job.job_id], attempts.get(job.job_id, 0))
    if ctx.cache is not None and len(good) == len(group):      # only a fully validated call is cached, under its first-attempt prompt
        try:
            ctx.cache.put(key, {"sentences": [{"job_id": j.job_id, "text": out[j.job_id].text, "claim_ids": out[j.job_id].claim_ids} for j in group]})
        except Exception:
            logger.warning("Stage 5 cache put failed", exc_info=True)
    return out


def write_section(section_title, jobs, *, llm=None, check=None, cache=None, progress=None, rate=None, tier_rules=None, fallback=None, retries=None):
    """Writes the sentences of one section. Returns (list[Sentence] in the order of `jobs`, stats dict). Never raises.

    llm       callable(messages, response_format, purpose) -> dict | (dict, usage); default `default_llm` (Groq)
    check     callable(text, claim_ids, job) -> [reason]; default `default_check`
    cache     None = disk cache per STAGE5_CACHE, False = off, or an object with get(key)/put(key, value)
    progress  callable(step, message, **data), called once per finished call; its errors are swallowed
    rate      a RateGuard (default: the shared `default_rate`)
    tier_rules  hedging.TIER_RULES (default: read from hedging.py); fallback  callable(job) (default: hedging.fallback_sentence)"""
    jobs = list(jobs or [])
    stats = new_stats()
    stats["jobs"] = len(jobs)
    try:
        rules = tier_rules if tier_rules is not None else default_tier_rules()
        ctx = _Ctx(section_title, llm, check or default_check, resolve_cache(cache), progress, rate or default_rate, rules, fallback,
                   settings.retries() if retries is None else max(0, int(retries)), stats)
        results = {}
        for group in split_jobs(section_title, jobs, rules):
            try:
                results.update(_run_group(group, ctx))
            except Exception:
                logger.exception("Stage 5: a call of section %r failed unexpectedly; its jobs use the fallback sentence", section_title)
                for j in group:
                    results[j.job_id] = _fallback_sentence(j, ctx, ["the writer failed unexpectedly"], 0)
            safe_progress(progress, "write", f"Wrote {len(group)} sentence(s) of \"{_clean(section_title)[:60]}\"", jobs=len(group), section=section_title)
        out = []
        for j in jobs:
            out.append(results.get(j.job_id) or _fallback_sentence(j, ctx, ["no sentence was produced"], 0))
        return out, stats
    except Exception:
        logger.exception("Stage 5: write_section failed unexpectedly; every job uses the fallback sentence")
        ctx = _Ctx(section_title, llm, check, None, None, None, None, fallback, 0, stats)
        return [_fallback_sentence(j, ctx, ["the writer failed unexpectedly"], 0) for j in jobs], stats


def write_sections(items, *, workers=None, **kwargs) -> list:
    """write_section for several sections on up to STAGE5_WORKERS threads. items = [(section_title, jobs)]; returns [(sentences, stats)] in the
    order of items, whichever thread finished first. kwargs go to write_section (llm, check, cache, progress, rate ...)."""
    items = list(items)
    n = settings.workers() if workers is None else max(1, int(workers))
    if len(items) <= 1 or n <= 1:
        return [write_section(t, j, **kwargs) for t, j in items]
    contexts = [contextvars.copy_context() for _ in items]
    with ThreadPoolExecutor(max_workers=min(n, len(items))) as pool:
        return list(pool.map(lambda cj: cj[0].run(write_section, cj[1][0], cj[1][1], **kwargs), zip(contexts, items)))
