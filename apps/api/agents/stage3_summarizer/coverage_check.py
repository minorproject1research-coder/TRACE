from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder
import hashlib
import logging
import os
from typing import List, Dict, Any, Set, Optional, Tuple

logger = logging.getLogger("apps.api.agents.stage3_summarizer.coverage_check")

# --- Constants ---
# How much one source counts toward `min_sources`, by what its digest was built from.
EVIDENCE_WEIGHT = {"full_text": 1.0, "abstract": 0.5, "web_snippet": 0.5}

# Minimum raw cosine similarity between aspect/claim for a tag to count as coverage.
MIN_TAG_SIM = 0.40

# An aspect is covered only if at least this many VERIFIED findings tagged "full" exist,
# from at least MIN_COVER_SOURCES distinct source IDs.
MIN_COVER_FINDINGS = 2
MIN_COVER_SOURCES = 2

# Judge-based coverage constants
JUDGE_MIN_YES = 2
JUDGE_ERROR_THRESHOLD = 0.30  # fallback if >30% items end as error


def one_finding_one_aspect_enabled() -> bool:
    """ONE_FINDING_ONE_ASPECT=true: a finding counts as covering evidence only for the aspect it is most similar to (default off)."""
    return os.getenv("ONE_FINDING_ONE_ASPECT", "false").strip().lower() in ("1", "true", "yes", "on")


def one_finding_margin() -> float:
    """ONE_FINDING_MARGIN (default 0): with a margin > 0 a "yes" is dropped only when another aspect is at least that much MORE similar."""
    try:
        return max(0.0, float(os.getenv("ONE_FINDING_MARGIN", "0") or 0))
    except ValueError:
        return 0.0


def assign_best_aspect(
    yes_by_aspect: Dict[int, List[Tuple[int, str, str]]],
    similarity: Dict[Tuple[int, str, str], float],
    margin: float = 0.0,
) -> Tuple[Dict[int, List[Tuple[int, str, str]]], int]:
    """Keep each finding's "yes" only for the aspect where it has the highest embedding similarity (ties: the lower aspect index).

    A finding is (source_id, claim_hash); keys are (aspect_idx, source_id, claim_hash). A claim judged "yes" for several aspects (one
    gradient-storage claim was "yes" for memory cost defined, measured and factors) then covers only one of them. Returns the filtered
    mapping and how many yes verdicts were dropped. With margin > 0 every aspect whose similarity is within `margin` of the best one is
    kept too (near-ties are not a reason to drop an answer). Pure function, no I/O."""
    best: Dict[Tuple[str, str], Tuple[float, int, Tuple[int, str, str]]] = {}
    for aspect_idx, keys in yes_by_aspect.items():
        for key in keys:
            rank = (similarity.get(key, 0.0), -aspect_idx)
            current = best.get((key[1], key[2]))
            if current is None or rank > (current[0], current[1]):
                best[(key[1], key[2])] = (rank[0], rank[1], key)
    keep = {v[2] for v in best.values()}
    if margin > 0:
        best_sim = {finding: v[0] for finding, v in best.items()}
        keep |= {k for keys in yes_by_aspect.values() for k in keys if similarity.get(k, 0.0) >= best_sim[(k[1], k[2])] - margin}
    kept = {a: [k for k in keys if k in keep] for a, keys in yes_by_aspect.items()}
    dropped = sum(len(keys) for keys in yes_by_aspect.values()) - sum(len(keys) for keys in kept.values())
    return kept, dropped


def _use_judge_coverage() -> bool:
    """Check if judge coverage should be used (reads env at runtime)."""
    return os.getenv("USE_JUDGE_COVERAGE", "true").lower() == "true"


def _extract_tags(finding: dict) -> list[dict]:
    """Extract tags from finding's answers_details.
    
    Returns list of {"detail": int (1-indexed), "strength": "full"|"partial"}.
    Handles both new format (objects) and legacy format (ints).
    """
    raw = finding.get("answers_details", [])
    if not isinstance(raw, list):
        return []
    
    tags = []
    for item in raw:
        if isinstance(item, int):
            # Legacy format
            tags.append({"detail": item, "strength": "partial"})
        elif isinstance(item, dict):
            detail = item.get("detail")
            strength = item.get("strength", "partial")
            if isinstance(detail, int) and detail >= 1:
                tags.append({"detail": detail, "strength": strength})
    return tags


def check_coverage(
    aspects: List[str],
    aspect_to_detail: List[int],
    original_details: List[str],
    digests: List[Dict[str, Any]],
    min_sources: int = 3,
    detail_sim: float = 0.6,
) -> Dict[str, Any]:
    """
    Stricter coverage check with aspects and tag strength.
    
    An ASPECT is covered only if:
    - At least MIN_COVER_FINDINGS verified findings tagged "full" for that aspect exist
    - From at least MIN_COVER_SOURCES distinct source IDs
    - Each passes MIN_TAG_SIM floor
    
    Partial tags never count toward coverage on their own (logged for audit).
    
    A DETAIL counts as covered only if ALL of its aspects are covered.
    uncovered_details lists the ORIGINAL detail text (not aspects).
    uncovered_aspects lists the uncovered aspect texts.
    """
    verified = [(d, f) for d in digests for f in d["findings"] if f["verified"]]
    by_source: Dict[str, str] = {}
    for d, _ in verified:
        by_source[d["source_id"]] = d.get("evidence_level") or "full_text"
    weighted_sources = sum(EVIDENCE_WEIGHT.get(level, 1.0) for level in by_source.values())

    # Check if ANY finding has answers_details key (legacy fallback detection)
    has_answers_details = any("answers_details" in f for d in digests for f in d["findings"])

    uncovered_aspects: List[str] = []
    uncovered_details: List[str] = []

    if verified and aspects:
        if has_answers_details:
            # Tag-based coverage with aspects
            n_aspects = len(aspects)
            aspect_covered = [False] * n_aspects
            aspect_full_tags = [0] * n_aspects
            aspect_partial_tags = [0] * n_aspects
            aspect_sources: List[Set[str]] = [set() for _ in range(n_aspects)]
            aspect_covering_findings: List[List[Dict[str, Any]]] = [[] for _ in range(n_aspects)]  # for audit

            # --- Performance optimization: batch encode all aspects once ---
            model = get_embedder()
            aspect_embeddings = model.encode(aspects, normalize_embeddings=True)

            # Collect all (aspect_idx, finding, claim) tuples that need similarity check
            checks = []  # list of (aspect_idx, finding, claim, strength, source_id, detail_num)
            for d, f in verified:
                source_id = d.get("source_id")
                tags = _extract_tags(f)
                
                for tag in tags:
                    detail_num = tag["detail"]
                    strength = tag.get("strength", "partial")
                    aspect_idx = detail_num - 1  # 0-indexed
                    
                    if aspect_idx < 0 or aspect_idx >= n_aspects:
                        continue
                    
                    claim = f.get("claim", "")
                    if not claim:
                        if strength == "partial":
                            aspect_partial_tags[aspect_idx] += 1
                        continue
                    
                    checks.append((aspect_idx, f, claim, strength, source_id, detail_num))

            # Batch encode all claims at once
            claim_texts = [c[2] for c in checks]  # claim is at index 2
            claim_embeddings = model.encode(claim_texts, normalize_embeddings=True) if claim_texts else []

            # Process checks using pre-computed embeddings
            aspect_covered = [False] * n_aspects
            aspect_full_tags = [0] * n_aspects
            aspect_partial_tags = [0] * n_aspects
            aspect_sources: List[Set[str]] = [set() for _ in range(n_aspects)]
            aspect_covering_findings: List[List[Dict[str, Any]]] = [[] for _ in range(n_aspects)]

            for idx, (aspect_idx, finding, claim, strength, source_id, detail_num) in enumerate(checks):
                # Get pre-computed embeddings
                aspect_emb = aspect_embeddings[aspect_idx]
                claim_emb = claim_embeddings[idx]
                sim = float(aspect_emb @ claim_emb)
                
                if sim < MIN_TAG_SIM:
                    logger.info(
                        "Tag rejected by MIN_TAG_SIM floor: aspect=%d sim=%.3f < %.2f claim='%s...'",
                        aspect_idx + 1, sim, MIN_TAG_SIM, claim[:60]
                    )
                    if strength == "partial":
                        aspect_partial_tags[aspect_idx] += 1
                    continue
                
                if strength == "full":
                    aspect_full_tags[aspect_idx] += 1
                    aspect_sources[aspect_idx].add(source_id)
                    aspect_covering_findings[aspect_idx].append({
                        "source_id": source_id,
                        "claim": claim[:80],
                        "sim": sim,
                    })
                else:
                    aspect_partial_tags[aspect_idx] += 1
            
            # Determine which aspects are covered
            aspect_covered = [False] * n_aspects
            for i in range(n_aspects):
                full_count = aspect_full_tags[i]
                source_count = len(aspect_sources[i])
                
                # Log audit info per aspect
                logger.info(
                    "Aspect %d ('%s...'): full_tags=%d partial_tags=%d sources=%d covering=%d",
                    i + 1, aspects[i][:50], aspect_full_tags[i], aspect_partial_tags[i],
                    source_count, len(aspect_covering_findings[i])
                )
                
                covered = (full_count >= MIN_COVER_FINDINGS and 
                          source_count >= MIN_COVER_SOURCES)
                if covered:
                    aspect_covered[i] = True
                    logger.info(
                        "Aspect %d covered: full_tags=%d sources=%d findings=%s",
                        i + 1, full_count, source_count,
                        aspect_covering_findings[i]
                    )
                else:
                    logger.info(
                        "Aspect %d UNCOVERED: full_tags=%d (need %d) sources=%d (need %d)",
                        i + 1, full_count, MIN_COVER_FINDINGS, source_count, MIN_COVER_SOURCES
                    )
            
            # Determine uncovered aspects
            uncovered_aspects = [aspects[i] for i, covered in enumerate(aspect_covered) if not covered]
            
            # Map uncovered aspects back to original details
            # A detail is uncovered if ANY of its aspects are uncovered
            n_details = len(original_details)
            detail_covered = [True] * n_details
            for i, covered in enumerate(aspect_covered):
                if not covered:
                    detail_idx = aspect_to_detail[i]
                    if detail_idx < n_details:
                        detail_covered[detail_idx] = False
            
            uncovered_details = [original_details[i] for i, covered in enumerate(detail_covered) if not covered]
        
        else:
            # Legacy similarity-based coverage (old logic)
            model = get_embedder()
            dq = model.encode(original_details, normalize_embeddings=True)
            fe = model.encode([f["claim"] for _, f in verified], normalize_embeddings=True)
            sims = dq @ fe.T
            uncovered_details = [q for i, q in enumerate(original_details) if sims[i].max() < detail_sim]
            uncovered_aspects = []
    else:
        uncovered_details = list(original_details)
        uncovered_aspects = []

    return {
        "sufficient": weighted_sources >= min_sources and not uncovered_details,
        "source_count": len(by_source),
        "full_text_source_count": sum(1 for level in by_source.values() if level == "full_text"),
        "uncovered_details": uncovered_details,
        "uncovered_aspects": uncovered_aspects,
    }


def _verdict_final(entry: Dict) -> str:
    return ((entry or {}).get("verdict") or {}).get("final") or "error"


def check_coverage_judged(
    aspects: List[str],
    aspect_to_detail: List[int],
    original_details: List[str],
    digests: List[Dict[str, Any]],
    judge_verdicts: Dict[Tuple[int, str, str], Dict],
    min_sources: int = 3,
    fallback: bool = True,
    candidates: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """
    Judge-based coverage check with explicit per-aspect states.

    Per-aspect states:
    - covered_judge: at least JUDGE_MIN_YES "yes" verdicts from at least MIN_COVER_SOURCES distinct sources
    - uncovered_judged: judged but not covered. Reason "judged_insufficient" (every candidate got a usable verdict, too few
      yes) or "no_candidates" (nothing was sent to the judge for this aspect: there was no evidence to judge)
    - unjudged: at least one candidate has no usable verdict (missing or "error") and the aspect is not covered

    Rules:
    - unjudged aspects count as NOT covered and make sufficient=False; they are listed in "unjudged_aspects", NOT in
      "uncovered_aspects" (so Loop 2 never generates queries for them)
    - fallback to the tag rule happens only for the WHOLE sub-question: judge disabled, candidates exist but no usable verdict came
      back (endpoint unreachable), or the error rate is above JUDGE_ERROR_THRESHOLD. A single aspect without candidates or
      verdicts never triggers it.
    - candidates=None means "unknown" (old callers): an empty verdict dict is then treated as an unreachable judge.
      candidates=[] means "nothing to judge": no fallback, every aspect is uncovered with reason no_candidates.
    - judge_used=True only if EVERY aspect was judged (no unjudged aspects)
    - never mixes judge and tag logic within a sub-question
    """
    verified = [(d, f) for d in digests for f in d["findings"] if f["verified"]]
    by_source: Dict[str, str] = {}
    for d, _ in verified:
        by_source[d["source_id"]] = d.get("evidence_level") or "full_text"
    weighted_sources = sum(EVIDENCE_WEIGHT.get(level, 1.0) for level in by_source.values())
    judge_verdicts = judge_verdicts or {}

    finals = [_verdict_final(v) for v in judge_verdicts.values()]
    total_items = len(finals)
    error_count = sum(1 for f in finals if f not in ("yes", "partial", "no"))
    judge_stats = {
        "candidates": total_items,
        "yes": finals.count("yes"),
        "partial": finals.count("partial"),
        "no": finals.count("no"),
        "error": error_count,
    }

    # Whole-sub-question decision: judge path or tag-rule fallback
    nothing_to_judge = candidates is not None and len(candidates) == 0 and total_items == 0
    fallback_reason = None
    if not _use_judge_coverage():
        fallback_reason = "judge disabled"
    elif nothing_to_judge:
        pass
    elif total_items == 0:
        fallback_reason = "judge unavailable (no verdicts)"
    elif error_count == total_items:
        fallback_reason = "judge unavailable (every verdict failed)"
    elif error_count / total_items > JUDGE_ERROR_THRESHOLD:
        fallback_reason = f"judge_error_rate_exceeded ({error_count / total_items:.1%} > {JUDGE_ERROR_THRESHOLD:.0%})"
        logger.warning("Judge fallback triggered: %s", fallback_reason)

    if fallback_reason:
        if fallback:
            logger.warning("Falling back to tag-based coverage: %s", fallback_reason)
            result = check_coverage(aspects, aspect_to_detail, original_details, digests, min_sources)
            result["judge_used"] = False
            result["judge_stats"] = judge_stats
            result["aspect_evidence"] = {}
            result["unjudged_aspects"] = []
            result["uncovered_reasons"] = {}
            result["fallback_reason"] = fallback_reason
            return result
        return {
            "sufficient": False,
            "source_count": len(by_source),
            "full_text_source_count": sum(1 for level in by_source.values() if level == "full_text"),
            "uncovered_details": list(original_details),
            "uncovered_aspects": list(aspects),
            "unjudged_aspects": list(aspects),
            "uncovered_reasons": {a: "endpoint_unreachable" for a in aspects},
            "judge_used": False,
            "judge_stats": judge_stats,
            "aspect_evidence": {},
            "fallback_reason": fallback_reason,
        }

    # Judge path. Candidate keys and evidence info are per (aspect, source, claim) so one claim judged for two aspects keeps
    # its own quote and item id.
    n_aspects = len(aspects)
    cand_keys: Dict[int, set] = {i: set() for i in range(n_aspects)}
    key_info: Dict[Tuple[int, str, str], Dict] = {}
    if candidates is not None:
        for c in candidates:
            key = (c["aspect_idx"], c["source_id"], hashlib.sha256(c["claim"].encode()).hexdigest()[:16])
            cand_keys.setdefault(c["aspect_idx"], set()).add(key)
            key_info[key] = {"claim": c["claim"], "quote": c["quote"], "item_id": c.get("item_id", "")}
    for key in judge_verdicts:   # verdicts without a matching candidate still count as candidates of their aspect
        cand_keys.setdefault(key[0], set()).add(key)

    aspect_covered = [False] * n_aspects
    aspect_evidence: Dict[int, List[Dict]] = {}
    unjudged_aspects: List[str] = []
    uncovered_reasons: Dict[str, str] = {}

    yes_by_aspect = {i: sorted(k for k in cand_keys.get(i, ()) if _verdict_final(judge_verdicts.get(k)) == "yes") for i in range(n_aspects)}
    one_to_one_dropped = None
    if one_finding_one_aspect_enabled():
        sims = {(c["aspect_idx"], c["source_id"], hashlib.sha256(c["claim"].encode()).hexdigest()[:16]): c.get("similarity", 0.0)
                for c in (candidates or [])}
        yes_by_aspect, one_to_one_dropped = assign_best_aspect(yes_by_aspect, sims, one_finding_margin())
        if one_to_one_dropped:
            logger.info("ONE_FINDING_ONE_ASPECT: %d yes verdict(s) not counted (finding is closer to another aspect)", one_to_one_dropped)

    for i in range(n_aspects):
        yes_keys = yes_by_aspect[i]
        yes_sources = {k[1] for k in yes_keys}
        evidence = []
        for k in sorted(yes_keys, key=lambda k: (k[1], k[2])):
            info = key_info.get(k, {})
            verdict = judge_verdicts[k].get("verdict", {})
            evidence.append({
                "source_id": k[1],
                "claim_prefix": info.get("claim", "")[:80],
                "quote_prefix": info.get("quote", "")[:80],
                "item_id": info.get("item_id", ""),
                "verdict": verdict.get("final"),
                "quote_supports_claim": verdict.get("quote_supports_claim"),
                "answers_aspect": verdict.get("answers_aspect"),
                "reason": verdict.get("reason"),
            })
        aspect_evidence[i] = evidence

        if len(yes_keys) >= JUDGE_MIN_YES and len(yes_sources) >= MIN_COVER_SOURCES:
            aspect_covered[i] = True
            logger.info("Aspect %d covered_judge: yes=%d sources=%d", i + 1, len(yes_keys), len(yes_sources))
            continue

        keys = cand_keys.get(i, set())
        unusable = [k for k in keys if _verdict_final(judge_verdicts.get(k)) not in ("yes", "partial", "no")]
        if not keys:
            uncovered_reasons[aspects[i]] = "no_candidates"
            logger.info("Aspect %d uncovered_judged: no_candidates", i + 1)
        elif unusable:
            unjudged_aspects.append(aspects[i])
            uncovered_reasons[aspects[i]] = "unjudged"
            logger.info("Aspect %d unjudged: %d of %d candidates without a usable verdict", i + 1, len(unusable), len(keys))
        else:
            uncovered_reasons[aspects[i]] = "judged_insufficient"
            logger.info("Aspect %d uncovered_judged: yes=%d (need %d) sources=%d (need %d)",
                        i + 1, len(yes_keys), JUDGE_MIN_YES, len(yes_sources), MIN_COVER_SOURCES)

    uncovered_aspects = [aspects[i] for i in range(n_aspects) if not aspect_covered[i] and aspects[i] not in unjudged_aspects]

    # A detail is covered only if ALL of its aspects are covered (uncovered_judged and unjudged both make it uncovered)
    n_details = len(original_details)
    detail_covered = [True] * n_details
    for i, covered in enumerate(aspect_covered):
        if not covered and aspect_to_detail[i] < n_details:
            detail_covered[aspect_to_detail[i]] = False
    uncovered_details = [original_details[i] for i, ok in enumerate(detail_covered) if not ok]

    return {
        "sufficient": weighted_sources >= min_sources and not uncovered_details,
        "source_count": len(by_source),
        "full_text_source_count": sum(1 for level in by_source.values() if level == "full_text"),
        "uncovered_details": uncovered_details,
        "uncovered_aspects": uncovered_aspects,
        "unjudged_aspects": unjudged_aspects,
        "uncovered_reasons": uncovered_reasons,
        "judge_used": not unjudged_aspects,
        "judge_stats": ({**judge_stats, "one_finding_one_aspect_dropped": one_to_one_dropped} if one_to_one_dropped is not None else judge_stats),
        "aspect_evidence": aspect_evidence,
    }


# Legacy function for backward compatibility with old calls
def check_coverage_legacy(detail_questions: List[str], digests: List[Dict[str, Any]],
                          min_sources: int = 3, detail_sim: float = 0.6) -> Dict[str, Any]:
    """Legacy coverage check using detail questions directly (no aspects)."""
    verified = [(d, f) for d in digests for f in d["findings"] if f["verified"]]
    by_source: Dict[str, str] = {}
    for d, _ in verified:
        by_source[d["source_id"]] = d.get("evidence_level") or "full_text"
    weighted_sources = sum(EVIDENCE_WEIGHT.get(level, 1.0) for level in by_source.values())

    has_answers_details = any("answers_details" in f for d in digests for f in d["findings"])

    uncovered: List[str] = []
    if verified and detail_questions:
        if has_answers_details:
            # Batch encode all detail questions
            model = get_embedder()
            detail_embeddings = model.encode(detail_questions, normalize_embeddings=True)
            
            for i, detail_q in enumerate(detail_questions):
                covered = False
                for d, f in verified:
                    tags = _extract_tags(f)
                    target = i + 1
                    for tag in tags:
                        if tag["detail"] == target:
                            # Check MIN_TAG_SIM
                            claim = f.get("claim", "")
                            if claim:
                                dq = detail_embeddings[i]
                                fc = model.encode([claim], normalize_embeddings=True)[0]
                                sim = float(dq @ fc)
                                if sim >= MIN_TAG_SIM:
                                    covered = True
                                    break
                    if not covered:
                        uncovered.append(detail_q)
        else:
            m = get_embedder()
            dq = m.encode(detail_questions, normalize_embeddings=True)
            fe = m.encode([f["claim"] for _, f in verified], normalize_embeddings=True)
            sims = dq @ fe.T
            uncovered = [q for i, q in enumerate(detail_questions) if sims[i].max() < detail_sim]
    else:
        uncovered = list(detail_questions)

    return {
        "sufficient": weighted_sources >= min_sources and not uncovered,
        "source_count": len(by_source),
        "full_text_source_count": sum(1 for level in by_source.values() if level == "full_text"),
        "uncovered_details": uncovered,
    }