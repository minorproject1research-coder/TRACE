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
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder

logger = logging.getLogger("apps.api.agents.stage3_summarizer.evidence_judge")

# --- Configuration constants (env-overridable, read at runtime) ---
def _get_config():
    return {
        "JUDGE_URL": os.getenv("JUDGE_URL", "").rstrip("/"),
        "API_KEY": os.getenv("JUDGE_API_KEY", ""),
        "JUDGE_MODEL_ID": os.getenv("JUDGE_MODEL_ID", "judge"),
        "JUDGE_CANDIDATES_PER_ASPECT": int(os.getenv("JUDGE_CANDIDATES_PER_ASPECT", "6")),
        "JUDGE_EXTRA_BY_SIM": int(os.getenv("JUDGE_EXTRA_BY_SIM", "2")),
        "JUDGE_BATCH_SIZE": int(os.getenv("JUDGE_BATCH_SIZE", "32")),
        "JUDGE_TIMEOUT_S": int(os.getenv("JUDGE_TIMEOUT_S", "120")),
        "JUDGE_RETRIES": int(os.getenv("JUDGE_RETRIES", "2")),
        "MAX_JUDGE_ITEMS_PER_SUBQ": int(os.getenv("MAX_JUDGE_ITEMS_PER_SUBQ", "60")),
        "CONTEXT_CHARS": int(os.getenv("JUDGE_CONTEXT_CHARS", "1200")),
        "NEAR_DUP_ASPECT_SIM": float(os.getenv("NEAR_DUP_ASPECT_SIM", "0.92")),
    }

JUDGE_CACHE_PATH = Path("reports/judge_cache.json")


# --- Cache helpers ---
def _load_judge_cache() -> Dict[str, Dict]:
    """Load judge verdict cache from JSON file."""
    cache = {}
    if JUDGE_CACHE_PATH.exists():
        try:
            with open(JUDGE_CACHE_PATH, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load judge cache: {e}")
    return cache


def _save_judge_cache(cache: Dict[str, Dict]) -> None:
    """Save judge verdict cache to JSON file."""
    JUDGE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(JUDGE_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
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
) -> List[Dict]:
    """
    Per aspect, collect VERIFIED findings tagged for that aspect (any strength),
    plus top JUDGE_EXTRA_BY_SIM verified findings by embedding similarity to the
    aspect text among findings NOT already included. Dedupe, rank by similarity,
    keep at most JUDGE_CANDIDATES_PER_ASPECT.

    Returns list of candidate dicts with keys:
    - aspect_idx, aspect_text, source_id, claim, quote, chunk_id, similarity, finding_idx,
      item_id (stable unique identifier for this candidate)
    """
    config = _get_config()
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
        for sim, vf_idx, source_id, claim, quote, chunk_id, d_idx, f_idx in extras[:config["JUDGE_EXTRA_BY_SIM"]]:
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
        # Trim lowest-similarity candidates evenly
        final_candidates.sort(key=lambda x: x["similarity"], reverse=True)
        trimmed = final_candidates[:config["MAX_JUDGE_ITEMS_PER_SUBQ"]]
        logger.warning(
            f"Trimmed judge candidates from {len(final_candidates)} to {config['MAX_JUDGE_ITEMS_PER_SUBQ']} "
            f"(lowest similarity: {trimmed[-1]['similarity']:.3f})"
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
        chunk_text = chunk_lookup.get(str(chunk_id), "") if chunk_id is not None else ""

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
        logger.warning("JUDGE_URL not configured, returning error verdicts")
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

    # Process in batches
    for i in range(0, len(to_judge), batch_size):
        batch = to_judge[i:i + batch_size]
        batch_items = [b[0] for b in batch]

        last_error = None
        for attempt in range(retries + 1):
            try:
                results = _call_judge_batch(batch_items, judge_url, api_key, timeout)
                break
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
                last_error = e
                if attempt < retries:
                    wait = 2 ** attempt
                    logger.warning(f"Judge call failed (attempt {attempt + 1}/{retries + 1}): {e}. Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    logger.error(f"Judge call failed after {retries + 1} attempts: {e}")
                    results = [{"error": str(e), "verdict": None, "raw_output": ""}] * len(batch_items)

        # Process results
        for (item, aspect_idx, source_id, claim_hash, cache_key), result in zip(batch, results):
            verdict = result.get("verdict")
            if verdict is None:
                verdict = {
                    "final": "error",
                    "quote_supports_claim": "error",
                    "answers_aspect": "error",
                    "reason": result.get("error", "Judge returned null verdict"),
                }
                verdicts[(aspect_idx, source_id, claim_hash)] = {
                    "verdict": verdict,
                    "raw_output": result.get("raw_output", ""),
                    "error": result.get("error"),
                }
            else:
                verdicts[(aspect_idx, source_id, claim_hash)] = {
                    "verdict": verdict,
                    "raw_output": result.get("raw_output", ""),
                    "error": result.get("error"),
                }
                # Cache successful verdicts
                cache[cache_key] = verdicts[(aspect_idx, source_id, claim_hash)]

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
    {"<aspect_idx>": {"final": ..., "quote_supports_claim": ..., "answers_aspect": ..., "reason": ...}}
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
) -> Tuple[List[Dict], Dict[Tuple[int, str, str], Dict]]:
    """
    Full pipeline: select candidates -> build items -> judge -> write verdicts.
    Returns (candidates, verdicts).
    """
    if not aspects or not digests:
        return [], {}

    candidates = select_candidates(aspects, digests, chunk_lookup, embedder)
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