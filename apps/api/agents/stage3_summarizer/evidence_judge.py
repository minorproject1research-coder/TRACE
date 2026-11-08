# apps/api/agents/stage3_summarizer/evidence_judge.py
"""
Independent judge for Stage 3 coverage decisions.

The digest generator's tags (answers_details with strength full/partial) are unreliable.
This module collects verified candidates per aspect, sends them to an external judge endpoint,
and writes verdicts back into the findings for auditable coverage decisions.
"""
import hashlib
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder
from apps.api.services import trace_llm_service

logger = logging.getLogger("apps.api.agents.stage3_summarizer.evidence_judge")

DEFAULT_JUDGE_PARALLEL = "2"


def _parallel_setting(value: Any) -> int:
    """JUDGE_PARALLEL as an int >= 1; an unreadable value means 1 (sequential, the safe behaviour)."""
    try:
        return max(1, int(str(value).strip()))
    except (TypeError, ValueError):
        return 1


# --- Configuration constants (env-overridable, read at runtime) ---
def _get_config():
    return {
        # The judge is the "judge" role of the same model server as the planner, so it uses TRACE_LLM_URL and TRACE_LLM_API_KEY.
        # JUDGE_URL / JUDGE_API_KEY are optional overrides (only needed if the judge ever runs somewhere else).
        "JUDGE_URL": (os.getenv("JUDGE_URL") or os.getenv("TRACE_LLM_URL") or "").strip().rstrip("/"),
        "API_KEY": os.getenv("JUDGE_API_KEY") or trace_llm_service.api_key(),
        "JUDGE_MODEL_ID": os.getenv("JUDGE_MODEL_ID", "judge"),
        "JUDGE_CANDIDATES_PER_ASPECT": int(os.getenv("JUDGE_CANDIDATES_PER_ASPECT", "6")),
        "JUDGE_EXTRA_BY_SIM": int(os.getenv("JUDGE_EXTRA_BY_SIM", "2")),
        "JUDGE_BATCH_SIZE": int(os.getenv("JUDGE_BATCH_SIZE", "32")),
        "JUDGE_TIMEOUT_S": int(os.getenv("JUDGE_TIMEOUT_S", "120")),
        "JUDGE_RETRIES": int(os.getenv("JUDGE_RETRIES", "2")),
        # batches sent to the judge server at the same time (1 = one after the other)
        "JUDGE_PARALLEL": _parallel_setting(os.getenv("JUDGE_PARALLEL", DEFAULT_JUDGE_PARALLEL)),
        "MAX_JUDGE_ITEMS_PER_SUBQ": int(os.getenv("MAX_JUDGE_ITEMS_PER_SUBQ", "60")),
        "CONTEXT_CHARS": int(os.getenv("JUDGE_CONTEXT_CHARS", "1200")),
        "NEAR_DUP_ASPECT_SIM": float(os.getenv("NEAR_DUP_ASPECT_SIM", "0.92")),
    }

JUDGE_CACHE_PATH = Path(os.getenv("JUDGE_CACHE_PATH", "reports/judge_cache.json"))


# --- Cache helpers ---
_cache_io_lock = threading.Lock()


def _read_judge_cache_file() -> Dict[str, Dict]:
    cache = {}
    if JUDGE_CACHE_PATH.exists():
        try:
            with open(JUDGE_CACHE_PATH, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load judge cache: {e}")
    return cache


def _load_judge_cache() -> Dict[str, Dict]:
    """Load judge verdict cache from JSON file."""
    with _cache_io_lock:
        return _read_judge_cache_file()


def _save_judge_cache(cache: Dict[str, Dict]) -> None:
    """Save judge verdict cache to JSON file. Several sub-questions are judged at the same time (STAGE3_SQ_WORKERS): each call loaded the
    file before its judging and saves after it, so a plain overwrite would drop the verdicts another call saved in between. The save
    therefore merges with the file as it is NOW (this call's entries win) under a lock, and replaces the file atomically."""
    JUDGE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _cache_io_lock:
        try:
            merged = _read_judge_cache_file()
            merged.update(cache)
            tmp = JUDGE_CACHE_PATH.with_name(JUDGE_CACHE_PATH.name + f".{os.getpid()}.{threading.get_ident()}.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(merged, f, ensure_ascii=False)
            try:
                os.replace(tmp, JUDGE_CACHE_PATH)
            except OSError:                       # Windows: the target is open in another process; fall back to a direct write
                with open(JUDGE_CACHE_PATH, "w", encoding="utf-8") as f:
                    json.dump(merged, f, ensure_ascii=False)
                try:
                    os.remove(tmp)
                except OSError:
                    pass
        except Exception as e:
            logger.warning(f"Failed to save judge cache: {e}")


def _cache_key(aspect: str, claim: str, quote: str) -> str:
    """Generate stable cache key from aspect, claim, quote, and judge model ID."""
    config = _get_config()
    content = f"{aspect}|{claim}|{quote}|{config['JUDGE_MODEL_ID']}"
    return hashlib.sha256(content.encode()).hexdigest()


# --- Candidate selection ---
def select_candidates(
    aspects: List[str],
    digests: List[Dict],
    chunk_lookup: Dict[str, str],
    embedder=None,
    topic_aspect_idx: Optional[int] = None,
    candidates_per_aspect: Optional[int] = None,
) -> List[Dict]:
    """
    candidates_per_aspect: overrides JUDGE_CANDIDATES_PER_ASPECT for this call (Loop 2 judges more findings per aspect once it added sources).
    topic_aspect_idx: index of the sub-question's own question when it is judged as an aspect (TOPIC_ASPECT=judge). No finding is tagged
    for it (the digest prompt never saw it), so its candidates are the JUDGE_CANDIDATES_PER_ASPECT most similar verified findings
    instead of the JUDGE_EXTRA_BY_SIM extras of the other aspects.

    Per aspect, collect VERIFIED findings tagged for that aspect (any strength),
    plus top JUDGE_EXTRA_BY_SIM verified findings by embedding similarity to the
    aspect text among findings NOT already included. Dedupe, rank by similarity,
    keep at most JUDGE_CANDIDATES_PER_ASPECT.

    Returns list of candidate dicts with keys:
    - aspect_idx, aspect_text, source_id, claim, quote, chunk_id, similarity, finding_idx,
      item_id (stable unique identifier for this candidate)
    """
    config = _get_config()
    if candidates_per_aspect:
        config = {**config, "JUDGE_CANDIDATES_PER_ASPECT": candidates_per_aspect}
    if embedder is None:
        embedder = get_embedder()

    # Collect all verified findings with their tags
    verified_findings = []  # (digest_idx, finding_idx, finding, source_id)
    for d_idx, d in enumerate(digests):
        source_id = d.get("source_id", f"src_{d_idx}")
        for f_idx, f in enumerate(d.get("findings", [])):
            if f.get("verified"):
                verified_findings.append((d_idx, f_idx, f, source_id))

    if not verified_findings or not aspects:
        return []

    # Encode all aspects once
    aspect_embeddings = embedder.encode(aspects, normalize_embeddings=True)

    # Encode all claims once
    claim_texts = [f.get("claim", "") for _, _, f, _ in verified_findings]
    claim_embeddings = embedder.encode(claim_texts, normalize_embeddings=True) if claim_texts else []

    candidates = []  # (aspect_idx, source_id, claim, quote, chunk_id, similarity, digest_idx, finding_idx)
    used_per_aspect = [set() for _ in aspects]  # track (source_id, finding_idx) pairs

    # 1. Tagged findings for each aspect (any strength)
    for vf_idx, (d_idx, f_idx, finding, source_id) in enumerate(verified_findings):
        tags = finding.get("answers_details", [])
        if not tags:
            continue
        claim = finding.get("claim", "")
        quote = finding.get("quote", "")
        chunk_id = finding.get("chunk_id")

        for tag in tags:
            detail_num = tag.get("detail") if isinstance(tag, dict) else tag
            if not isinstance(detail_num, int):
                continue
            aspect_idx = detail_num - 1  # 0-indexed
            if 0 <= aspect_idx < len(aspects):
                key = (source_id, f_idx)
                if key in used_per_aspect[aspect_idx]:
                    continue
                used_per_aspect[aspect_idx].add(key)
                # Compute similarity to this aspect using pre-computed embeddings
                sim = float(aspect_embeddings[aspect_idx] @ claim_embeddings[vf_idx])
                candidates.append({
                    "aspect_idx": aspect_idx,
                    "aspect_text": aspects[aspect_idx],
                    "source_id": source_id,
                    "claim": claim,
                    "quote": quote,
                    "chunk_id": chunk_id,
                    "similarity": sim,
                    "digest_idx": d_idx,
                    "finding_idx": f_idx,
                    "from_tag": True,
                })

    # 2. Extra by similarity for each aspect (findings not already included)
    for aspect_idx, aspect_text in enumerate(aspects):
        aspect_emb = aspect_embeddings[aspect_idx]
        extras = []
        for vf_idx, (d_idx, f_idx, finding, source_id) in enumerate(verified_findings):
            key = (source_id, f_idx)
            if key in used_per_aspect[aspect_idx]:
                continue
            claim = finding.get("claim", "")
            quote = finding.get("quote", "")
            chunk_id = finding.get("chunk_id")
            if not claim or not quote:
                continue
            sim = float(aspect_emb @ claim_embeddings[vf_idx])
            extras.append((sim, vf_idx, source_id, claim, quote, chunk_id, d_idx, f_idx))

        # Sort by similarity descending, take top JUDGE_EXTRA_BY_SIM
        extras.sort(key=lambda x: x[0], reverse=True)
        n_extra = config["JUDGE_CANDIDATES_PER_ASPECT"] if aspect_idx == topic_aspect_idx else config["JUDGE_EXTRA_BY_SIM"]
        for sim, vf_idx, source_id, claim, quote, chunk_id, d_idx, f_idx in extras[:n_extra]:
            used_per_aspect[aspect_idx].add((source_id, f_idx))
            candidates.append({
                "aspect_idx": aspect_idx,
                "aspect_text": aspect_text,
                "source_id": source_id,
                "claim": claim,
                "quote": quote,
                "chunk_id": chunk_id,
                "similarity": sim,
                "digest_idx": d_idx,
                "finding_idx": f_idx,
                "from_tag": False,
            })

    # 3. Dedupe by (aspect_idx, source_id, claim_hash) and cap per aspect
    claim_hashes = {}
    for c in candidates:
        h = hashlib.sha256(c["claim"].encode()).hexdigest()[:16]
        key = (c["aspect_idx"], c["source_id"], h)
        if key not in claim_hashes or c["similarity"] > claim_hashes[key]["similarity"]:
            claim_hashes[key] = c

    # Group by aspect and cap
    by_aspect = {}
    for c in claim_hashes.values():
        by_aspect.setdefault(c["aspect_idx"], []).append(c)

    final_candidates = []
    for aspect_idx, clist in by_aspect.items():
        clist.sort(key=lambda x: x["similarity"], reverse=True)
        final_candidates.extend(clist[:config["JUDGE_CANDIDATES_PER_ASPECT"]])

    # 4. Global cap across aspects
    if len(final_candidates) > config["MAX_JUDGE_ITEMS_PER_SUBQ"]:
        # Trim by rank within each aspect, not by raw similarity: the best candidate of every aspect first, then the second best
        # of every aspect, and so on until the cap is reached. Sorting all candidates together could drop every candidate of an
        # aspect whose claims are less similar to it (planned item B6) and make the aspect look "uncovered" without being judged.
        cap = config["MAX_JUDGE_ITEMS_PER_SUBQ"]
        ranked = []
        for aspect_idx in sorted(by_aspect):
            own = sorted((c for c in final_candidates if c["aspect_idx"] == aspect_idx), key=lambda x: x["similarity"], reverse=True)
            ranked.extend((rank, -c["similarity"], c) for rank, c in enumerate(own))
        ranked.sort(key=lambda t: (t[0], t[1]))
        trimmed = [c for _, _, c in ranked[:cap]]
        logger.warning(
            f"Trimmed judge candidates from {len(final_candidates)} to {cap} "
            f"(lowest similarity kept: {min((c['similarity'] for c in trimmed), default=0.0):.3f}; aspects left without a candidate: "
            f"{len(by_aspect) - len({c['aspect_idx'] for c in trimmed})})"
        )
        final_candidates = trimmed

    # 5. Assign stable item_id to each candidate: hash of aspect_text + source_id + finding_idx
    # This provides a stable identifier that survives claim text changes and trimming
    for c in final_candidates:
        stable_content = f"{c['aspect_text']}|{c['source_id']}|{c['finding_idx']}"
        c["item_id"] = hashlib.sha256(stable_content.encode()).hexdigest()[:16]

    return final_candidates


# --- Build judge items with context ---
def build_judge_items(candidates: List[Dict], chunk_lookup: Dict[str, str]) -> List[Dict]:
    """
    Build items for the judge API.
    Each item: id (stable item_id), aspect, claim, quote, context (chunk text around quote).
    """
    config = _get_config()
    items = []
    for c in candidates:
        chunk_id = c.get("chunk_id")
        # chunk ids are positions inside ONE source's chunk list, so the lookup key is "<source_id>:<chunk_id>"; the plain "<chunk_id>"
        # key is only a fallback for old callers (it collides across sources and gives the judge another paper's passage)
        chunk_text = ""
        if chunk_id is not None:
            chunk_text = chunk_lookup.get(f"{c['source_id']}:{chunk_id}") or chunk_lookup.get(str(chunk_id), "")

        # Find quote position in chunk, extract CONTEXT_CHARS around it
        quote = c["quote"]
        context = ""
        if chunk_text and quote:
            q_norm = quote.replace("-\n", "").replace("\u00ad", "").lower()
            c_norm = chunk_text.replace("-\n", "").replace("\u00ad", "").lower()
            import re
            q_norm = re.sub(r"\s+", " ", q_norm).strip()
            c_norm = re.sub(r"\s+", " ", c_norm).strip()
            pos = c_norm.find(q_norm)
            if pos >= 0:
                half = config["CONTEXT_CHARS"] // 2
                start = max(0, pos - half)
                end = min(len(chunk_text), pos + len(quote) + half)
                context = chunk_text[start:end]
            else:
                context = chunk_text[:config["CONTEXT_CHARS"]]
        elif chunk_text:
            context = chunk_text[:config["CONTEXT_CHARS"]]

        # Use stable item_id from candidate, and include aspect_idx and source_id for verdict key construction
        item_id = c["item_id"]
        items.append({
            "id": item_id,
            "aspect_idx": c["aspect_idx"],
            "source_id": c["source_id"],
            "aspect": c["aspect_text"],
            "claim": c["claim"],
            "quote": c["quote"],
            "context": context,
        })
    return items


# --- Judge API call with retries and caching ---
def _call_judge_batch(
    items: List[Dict],
    judge_url: str,
    api_key: str,
    timeout: int,
) -> List[Dict]:
    """Call judge endpoint for a batch of items. Returns results list (same order)."""
    import time
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key

    payload = {
        "items": items,
        "max_new_tokens": 200,
        "thinking": False,
    }

    start_time = time.time()
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(f"{judge_url}/verify_evidence_batch", headers=headers, json=payload)
        latency_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Judge batch: status={resp.status_code}, latency_ms={latency_ms}, items={len(items)}")
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.warning(f"Judge batch failed: exception={type(e).__name__}, latency_ms={latency_ms}, items={len(items)}")
        raise


def judge_candidates(
    items: List[Dict],
    judge_url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: Optional[int] = None,
    retries: Optional[int] = None,
    batch_size: Optional[int] = None,
) -> Dict[Tuple[int, str, str], Dict]:
    """
    Send items to judge in batches with retries. Returns dict keyed by
    (aspect_idx, source_id, claim_hash) with verdict dict.
    
    Items must have a stable 'id' field (the item_id from candidates).
    The item_id is a hash of aspect_text + source_id + finding_idx.
    We also store aspect_idx and source_id in the item for verdict key construction.
    """
    config = _get_config()
    judge_url = judge_url or config["JUDGE_URL"]
    api_key = api_key or config["API_KEY"]
    timeout = timeout or config["JUDGE_TIMEOUT_S"]
    retries = retries if retries is not None else config["JUDGE_RETRIES"]
    batch_size = batch_size or config["JUDGE_BATCH_SIZE"]

    if not judge_url:
        logger.warning("judge URL not configured (set TRACE_LLM_URL), returning error verdicts")
        return {
            (0, "src", hashlib.sha256(item["claim"].encode()).hexdigest()[:16]): {
                "verdict": {"final": "error", "quote_supports_claim": "error", "answers_aspect": "error", "reason": "JUDGE_URL not configured"},
                "raw_output": "",
                "error": "JUDGE_URL not configured",
            }
            for item in items
        }

    # Load cache
    cache = _load_judge_cache()
    cache_hits = 0

    # Prepare items with cache keys and verdict keys
    # Items now have stable 'id' (item_id from candidate) and we store aspect_idx, source_id in the item
    items_with_keys = []
    for item in items:
        # Items now have: id (stable item_id), aspect_idx, source_id, claim, aspect, quote
        aspect_idx = item.get("aspect_idx")
        source_id = item.get("source_id")
        if aspect_idx is None or source_id is None:
            # Fallback for backward compatibility - parse from old-style ID
            id_str = item["id"]
            if id_str.startswith("a") and "_s" in id_str and "_f" in id_str:
                aspect_idx_str = id_str[1:id_str.index("_s")]
                aspect_idx = int(aspect_idx_str)
                s_start = id_str.index("_s") + 2
                f_start = id_str.index("_f", s_start)
                source_id = id_str[s_start:f_start]
            else:
                parts = id_str.split("_")
                aspect_idx = int(parts[0][1:]) if parts[0].startswith("a") else 0
                source_id = parts[1][1:] if len(parts) > 1 and parts[1].startswith("s") else "src"
        
        claim_hash = hashlib.sha256(item["claim"].encode()).hexdigest()[:16]
        cache_key = _cache_key(item["aspect"], item["claim"], item["quote"])
        items_with_keys.append((item, aspect_idx, source_id, claim_hash, cache_key))

    verdicts = {}
    to_judge = []

    for item, aspect_idx, source_id, claim_hash, cache_key in items_with_keys:
        if cache_key in cache:
            cached = cache[cache_key]
            verdicts[(aspect_idx, source_id, claim_hash)] = cached
            cache_hits += 1
        else:
            to_judge.append((item, aspect_idx, source_id, claim_hash, cache_key))

    if cache_hits:
        logger.info(f"Judge cache hits: {cache_hits}/{len(items)}")

    # Process in batches. Each batch has its own retry loop; with JUDGE_PARALLEL > 1 several batches are in flight at once,
    # but the results are always processed in the original batch order, so the output equals the sequential one.
    batches = [to_judge[i:i + batch_size] for i in range(0, len(to_judge), batch_size)]

    def _judge_batch_with_retries(batch: List[Tuple]) -> List[Dict]:
        batch_items = [b[0] for b in batch]
        for attempt in range(retries + 1):
            try:
                return _call_judge_batch(batch_items, judge_url, api_key, timeout)
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
                if attempt < retries:
                    wait = 2 ** attempt
                    logger.warning(f"Judge call failed (attempt {attempt + 1}/{retries + 1}): {e}. Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    logger.error(f"Judge call failed after {retries + 1} attempts: {e}")
                    return [{"error": str(e), "verdict": None, "raw_output": ""}] * len(batch_items)
        return []  # unreachable: the loop returns on success and on the last failed attempt

    workers = min(config["JUDGE_PARALLEL"], len(batches))
    executor = None
    if workers > 1:
        logger.info("Judge: %d batch(es) of up to %d item(s), %d at a time", len(batches), batch_size, workers)
        executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="judge")
        futures = [executor.submit(_judge_batch_with_retries, b) for b in batches]
        batch_results = (f.result() for f in futures)
    else:
        batch_results = (_judge_batch_with_retries(b) for b in batches)

    try:
        for batch, results in zip(batches, batch_results):
            # Process results. A server that returns fewer results than items must not make the rest vanish without a trace.
            if len(results) != len(batch):
                logger.warning("Judge returned %d result(s) for %d item(s); the missing ones are recorded as errors", len(results), len(batch))
                results = list(results) + [{"verdict": None, "error": "the server returned no result for this item", "raw_output": ""}] * (len(batch) - len(results))
            failed_in_batch = 0
            for (item, aspect_idx, source_id, claim_hash, cache_key), result in zip(batch, results):
                verdict = result.get("verdict")
                if verdict is None:
                    failed_in_batch += 1
                    # `error` can be present but empty/null; never store an empty reason (that made a failure impossible to diagnose)
                    raw = (result.get("raw_output") or "").strip().replace("\n", " ")
                    why = result.get("error") or "the judge returned no verdict and gave no error text"
                    if raw:
                        why = f"{why} | raw output: {raw[:160]}"
                    logger.warning("Judge verdict failed: aspect %d, source %s, claim '%s': %s",
                                   aspect_idx + 1, str(source_id)[:12], item["claim"][:70], why)
                    verdict = {
                        "final": "error",
                        "quote_supports_claim": "error",
                        "answers_aspect": "error",
                        "reason": why,
                    }
                    verdicts[(aspect_idx, source_id, claim_hash)] = {
                        "verdict": verdict,
                        "raw_output": result.get("raw_output", ""),
                        "error": result.get("error") or why,
                    }
                else:
                    verdicts[(aspect_idx, source_id, claim_hash)] = {
                        "verdict": verdict,
                        "raw_output": result.get("raw_output", ""),
                        "error": result.get("error"),
                    }
                    # Cache successful verdicts
                    cache[cache_key] = verdicts[(aspect_idx, source_id, claim_hash)]
            if failed_in_batch:
                logger.warning("Judge: %d of %d item(s) in this batch failed", failed_in_batch, len(batch))
    finally:
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)

    # Save updated cache
    _save_judge_cache(cache)

    return verdicts


# --- Write verdicts back into findings ---
def write_verdicts_to_findings(
    digests: List[Dict],
    candidates: List[Dict],
    verdicts: Dict[Tuple[int, str, str], Dict],
) -> None:
    """
    Inject judge verdicts into digests.findings JSON under new key "judge":
    {"<aspect_idx>": {"aspect": <text>, "final": ..., "quote_supports_claim": ..., "answers_aspect": ..., "reason": ...}}
    """
    for c in candidates:
        aspect_idx = c["aspect_idx"]
        source_id = c["source_id"]
        claim_hash = hashlib.sha256(c["claim"].encode()).hexdigest()[:16]
        key = (aspect_idx, source_id, claim_hash)

        if key not in verdicts:
            continue

        v = verdicts[key].get("verdict", {})
        if not v:
            continue

        d_idx = c["digest_idx"]
        f_idx = c["finding_idx"]

        if 0 <= d_idx < len(digests) and 0 <= f_idx < len(digests[d_idx].get("findings", [])):
            finding = digests[d_idx]["findings"][f_idx]
            if "judge" not in finding:
                finding["judge"] = {}
            finding["judge"][str(aspect_idx)] = {
                "aspect": c["aspect_text"],          # the exact aspect text the judge saw (aspect splits are LLM output and can change between runs)
                "final": v.get("final"),
                "quote_supports_claim": v.get("quote_supports_claim"),
                "answers_aspect": v.get("answers_aspect"),
                "reason": v.get("reason"),
            }


# --- Main entry point for orchestrator ---
def run_judge_for_subquestion(
    aspects: List[str],
    digests: List[Dict],
    chunk_lookup: Dict[str, str],
    embedder=None,
    topic_aspect_idx: Optional[int] = None,
    candidates_per_aspect: Optional[int] = None,
) -> Tuple[List[Dict], Dict[Tuple[int, str, str], Dict]]:
    """
    Full pipeline: select candidates -> build items -> judge -> write verdicts.
    Returns (candidates, verdicts).
    """
    if not aspects or not digests:
        return [], {}

    candidates = select_candidates(aspects, digests, chunk_lookup, embedder, topic_aspect_idx=topic_aspect_idx,
                                   candidates_per_aspect=candidates_per_aspect)
    if not candidates:
        logger.info("No candidates for judge")
        return [], {}

    items = build_judge_items(candidates, chunk_lookup)
    verdicts = judge_candidates(items)
    write_verdicts_to_findings(digests, candidates, verdicts)

    # Log stats
    stats = {"candidates": len(candidates), "yes": 0, "partial": 0, "no": 0, "error": 0}
    for v in verdicts.values():
        final = v.get("verdict", {}).get("final", "error")
        stats[final] = stats.get(final, 0) + 1
    logger.info(f"Judge stats: {stats}")

    return candidates, verdicts