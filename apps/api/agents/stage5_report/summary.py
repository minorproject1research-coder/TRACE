"""Executive summary and conclusion of Stage 5: a COMPRESS-ONLY task. The LLM never sees evidence, only numbered sentences that already passed
every check, and answers with 3-5 (summary) or 3-4 (conclusion) sentences that each name the numbered sentences they are based on.

Python decides everything that matters:
  - which validated sentences go in (highest tier first, at most MAX_BODY, in report order),
  - the claim ids of a summary sentence (the union of the claim ids of the sentences it names; the LLM does not write ids),
  - the tier of a summary sentence (the WEAKEST tier among the sentences it names),
  - whether it is accepted: `check_summary(summary_sentences, body_sentences) -> [reason]` (default validators.check_summary: every number and
    name must be in the body sentences, the hedge may not be stronger than the weakest source sentence, the length).
One retry with the Python reasons, then the EXTRACTIVE TEMPLATE: the highest-tier validated sentences copied word for word (no new text).
With no more sentences than the minimum there is nothing to compress: the extractive template is used at once, without an LLM call.

Shapes passed to `check_summary`:
  summary_sentences  [{"text": str, "from_sentences": [int, ...]}]            (the numbers are the 1-based `n` of the body sentences)
  body_sentences     [{"n": int, "text": str, "tier": str, "claim_ids": [...], "job_id": str}]
"""
import logging

from apps.api.agents.stage5_report import prompts, settings, writer
from apps.api.agents.stage5_report.schema import (ORIGIN_FALLBACK, ORIGIN_LLM, ORIGIN_TEMPLATE, TIER_PARTLY, TIER_SINGLE, TIER_SUPPORTED, Sentence)

logger = logging.getLogger("apps.api.agents.stage5_report")

SUMMARY_RANGE = (3, 5)
CONCLUSION_RANGE = (3, 4)
MAX_BODY = 14                       # at most this many body sentences are shown to the model
EXTRACTIVE_COUNT = {"summary": 4, "conclusion": 3}
TIER_PRIORITY = {TIER_SUPPORTED: 0, TIER_PARTLY: 1, TIER_SINGLE: 2}      # lower = better evidence = picked first
TIER_STRENGTH = {TIER_SUPPORTED: 3, TIER_PARTLY: 2, TIER_SINGLE: 1}      # the weakest tier of the sentences a summary sentence rests on wins


def select_body(validated_sentences, limit=None) -> list:
    """The body sentences offered to the model: highest tier first, at most `limit`, then back in report order, numbered from 1.
    Returns [{"n","text","tier","claim_ids","job_id"}]."""
    limit = MAX_BODY if limit is None else limit
    indexed = [(i, s) for i, s in enumerate(validated_sentences or []) if str(getattr(s, "text", "")).strip()]
    chosen = sorted(indexed, key=lambda p: (TIER_PRIORITY.get(p[1].tier, 9), p[0]))[:limit]
    chosen.sort(key=lambda p: p[0])
    return [{"n": n, "text": s.text, "tier": s.tier, "claim_ids": list(s.claim_ids), "job_id": s.job_id} for n, (_, s) in enumerate(chosen, start=1)]


def default_check_summary(summary_sentences, body_sentences) -> list:
    """validators.check_summary; a missing module fails closed (the extractive template is then used)."""
    try:
        from apps.api.agents.stage5_report import validators
        return list(validators.check_summary(summary_sentences, body_sentences) or [])
    except Exception as e:
        logger.warning("Stage 5 summary check failed to run: %s", e)
        return [f"the summary check could not run ({type(e).__name__}); the summary cannot be accepted"]


def _items(data, valid_numbers):
    """(list of {"text","from_sentences"}, reasons) from a parsed reply. Reasons say what is wrong with its shape."""
    raw = data.get("sentences") if isinstance(data, dict) else None
    if not isinstance(raw, list) or not raw:
        return [], ["the reply had no 'sentences' list"]
    items, reasons = [], []
    for k, it in enumerate(raw, start=1):
        text = it.get("text") if isinstance(it, dict) else None
        src = it.get("from_sentences") if isinstance(it, dict) else None
        if not isinstance(text, str) or not text.strip():
            reasons.append(f"sentence {k} is empty")
            continue
        if not isinstance(src, list) or not src or not all(isinstance(x, int) and not isinstance(x, bool) for x in src):
            reasons.append(f"sentence {k} must list the numbers of the sentences it is based on in from_sentences")
            continue
        bad = [x for x in src if x not in valid_numbers]
        if bad:
            reasons.append(f"sentence {k} names sentence number(s) {bad} that do not exist")
            continue
        items.append({"text": " ".join(text.split()), "from_sentences": list(dict.fromkeys(src))})
    return items, reasons


def _validate(data, body, low, high, check_summary):
    items, reasons = _items(data, {b["n"] for b in body})
    if reasons:
        return items, reasons
    if not low <= len(items) <= high:
        return items, [f"write between {low} and {high} sentences; you wrote {len(items)}"]
    try:
        reasons = [str(r) for r in (check_summary(items, body) or [])]
    except Exception as e:
        logger.warning("Stage 5 summary check raised: %s", e)
        reasons = [f"the summary check could not run ({type(e).__name__})"]
    return items, reasons


def _build_sentences(kind, items, body, attempts, reasons) -> list:
    by_n = {b["n"]: b for b in body}
    out = []
    for k, it in enumerate(items, start=1):
        src = [by_n[n] for n in it["from_sentences"]]
        ids = list(dict.fromkeys(i for b in src for i in b["claim_ids"]))
        weakest = min((b["tier"] for b in src), key=lambda t: TIER_STRENGTH.get(t, 0))
        out.append(Sentence(text=it["text"], claim_ids=ids, job_id=f"{kind}_{k}", tier=weakest, origin=ORIGIN_LLM, attempts=attempts, reasons=list(reasons)))
    return out


def extractive(kind: str, body, origin=ORIGIN_FALLBACK, attempts=0, reasons=None) -> list:
    """The template: the highest-tier body sentences, word for word (nothing new), in report order."""
    count = EXTRACTIVE_COUNT.get(kind, 3)
    pick = sorted(body, key=lambda b: (TIER_PRIORITY.get(b["tier"], 9), b["n"]))[:count]
    pick.sort(key=lambda b: b["n"])
    return [Sentence(text=b["text"], claim_ids=list(b["claim_ids"]), job_id=f"{kind}_{k}", tier=b["tier"], origin=origin, attempts=attempts,
                     reasons=list(reasons or [])) for k, b in enumerate(pick, start=1)]


def _compress(kind, validated_sentences, *, llm, check_summary, cache, progress, rate, retries, limit):
    stats = writer.new_stats()
    body = select_body(validated_sentences, limit)
    stats["jobs"] = 1 if body else 0
    if not body:
        stats["skipped"] += 1
        return [], stats
    low, high = SUMMARY_RANGE if kind == "summary" else CONCLUSION_RANGE
    if len(body) <= low:                          # nothing to compress: copy them (no LLM call, no new text)
        stats["extractive"] += 1
        return extractive(kind, body, origin=ORIGIN_TEMPLATE), stats
    check_summary = check_summary or default_check_summary
    retries = settings.retries() if retries is None else max(0, int(retries))
    cache = writer.resolve_cache(cache)
    shown = [{"n": b["n"], "text": b["text"], "tier": b["tier"]} for b in body]
    numbers = [b["n"] for b in body]
    first = prompts.summary_messages(kind, shown, low, high)
    key = writer.cache_key(first)
    if cache is not None:
        try:
            stored = cache.get(key)
        except Exception:
            stored = None
        if isinstance(stored, dict):
            items, reasons = _validate(stored, body, low, high, check_summary)         # a hit is validated again
            if not reasons:
                stats["cache_hits"] += 1
                return _build_sentences(kind, items, body, 1, []), stats
    purpose = writer.PURPOSE_SUMMARY
    log, previous, made = [], [], 0
    for attempt in range(1, retries + 2):
        messages = first if attempt == 1 else prompts.summary_retry_messages(kind, shown, low, high, previous, log[-8:])
        if attempt > 1:
            stats["retried"] += 1
        made += 1
        try:
            data = writer.call_llm(llm, messages, prompts.summary_schema(numbers), purpose, rate=rate, stats=stats)
        except writer.MalformedReply as e:
            stats["malformed"] += 1
            log.append(f"the reply was not usable JSON ({str(e)[:80]}); return the JSON object exactly as specified")
            logger.info("Stage 5: the %s reply was not usable JSON at attempt %d: %s", kind, attempt, str(e)[:200])
            continue
        except Exception as e:                  # LLMUnavailable, a network error, TooLarge: no point asking again
            if not isinstance(e, writer.LLMUnavailable):
                stats["llm_errors"] += 1
            log.append(f"the model call failed ({type(e).__name__})")
            logger.warning("Stage 5: the %s model call failed at attempt %d: %s: %s", kind, attempt, type(e).__name__, str(e)[:200])
            break
        items, reasons = _validate(data, body, low, high, check_summary)
        if not reasons:
            if cache is not None:
                try:
                    cache.put(key, {"sentences": [{"text": i["text"], "from_sentences": i["from_sentences"]} for i in items]})
                except Exception:
                    logger.warning("Stage 5 cache put failed", exc_info=True)
            writer.safe_progress(progress, kind, f"Wrote the {kind} ({len(items)} sentences)", sentences=len(items))
            return _build_sentences(kind, items, body, attempt, log), stats
        log.extend(reasons)
        logger.info("Stage 5: the %s was rejected at attempt %d: %s", kind, attempt, " | ".join(str(r)[:220] for r in reasons[:6]))
        previous = [i["text"] for i in items]
    stats["fallback"] += 1
    writer.safe_progress(progress, kind, f"The {kind} used the extractive template", sentences=len(body))
    return extractive(kind, body, attempts=made, reasons=log), stats


def write_summary(validated_sentences, *, llm=None, check_summary=None, cache=None, progress=None, rate=None, retries=None, limit=None):
    """The executive summary (3-5 sentences) from the validated body sentences (list[Sentence]). Returns (list[Sentence], stats); never raises.
    The result sentences carry claim_ids (union of what they are based on) and the weakest tier of their sources; job_id is summary_1 ..."""
    return _safe("summary", validated_sentences, llm, check_summary, cache, progress, rate, retries, limit)


def write_conclusion(validated_sentences, *, llm=None, check_summary=None, cache=None, progress=None, rate=None, retries=None, limit=None):
    """The conclusion (3-4 sentences), the same compress-only task with its own wording. Returns (list[Sentence], stats); never raises."""
    return _safe("conclusion", validated_sentences, llm, check_summary, cache, progress, rate, retries, limit)


def _safe(kind, validated, llm, check_summary, cache, progress, rate, retries, limit):
    try:
        return _compress(kind, validated, llm=llm, check_summary=check_summary, cache=cache, progress=progress, rate=rate, retries=retries, limit=limit)
    except Exception:
        logger.exception("Stage 5: the %s failed unexpectedly; using the extractive template", kind)
        stats = writer.new_stats()
        stats["fallback"] += 1
        try:
            return extractive(kind, select_body(validated, limit), reasons=["the writer failed unexpectedly"]), stats
        except Exception:
            return [], stats
