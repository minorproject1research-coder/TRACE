from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder
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


def check_coverage_judged(
    aspects: List[str],
    aspect_to_detail: List[int],
    original_details: List[str],
    digests: List[Dict[str, Any]],
    judge_verdicts: Dict[Tuple[int, str, str], Dict],
    min_sources: int = 3,
    fallback: bool = True,
) -> Dict[str, Any]:
    """
    Judge-based coverage check with explicit per-aspect states.
    
    Per-aspect states:
    - covered_judge: at least JUDGE_MIN_YES "yes" verdicts from at least MIN_COVER_SOURCES distinct sources
    - uncovered_judged: judged but fewer than JUDGE_MIN_YES qualifying "yes" or not enough distinct sources
    - unjudged: verdicts missing after retries (verdict missing or "error")
    
    Rules:
    - unjudged aspects count as NOT covered and make sufficient=False
    - unjudged aspects listed in new key "unjudged_aspects", NOT in "uncovered_aspects"
    - uncovered_reasons: {aspect_text: "no_candidates" | "judged_insufficient"} for uncovered aspects
    - Fallback to tag-based rule only when endpoint completely unreachable (zero verdicts for whole sub-question)
    - judge_used=True only if EVERY aspect was judged (no unjudged aspects)
    - Never mix judge and tag logic within a sub-question
    """
    verified = [(d, f) for d in digests for f in d["findings"] if f["verified"]]
    by_source: Dict[str, str] = {}
    for d, _ in verified:
        by_source[d["source_id"]] = d.get("evidence_level") or "full_text"
    weighted_sources = sum(EVIDENCE_WEIGHT.get(level, 1.0) for level in by_source.values())

    # Judge stats
    total_items = len(judge_verdicts) if judge_verdicts else 0
    yes_count = sum(1 for v in (judge_verdicts or {}).values() if v.get("verdict", {}).get("final") == "yes")
    partial_count = sum(1 for v in (judge_verdicts or {}).values() if v.get("verdict", {}).get("final") == "partial")
    no_count = sum(1 for v in (judge_verdicts or {}).values() if v.get("verdict", {}).get("final") == "no")
    error_count = sum(1 for v in (judge_verdicts or {}).values() if v.get("verdict", {}).get("final") == "error")
    
    judge_stats = {
        "candidates": total_items,
        "yes": yes_count,
        "partial": partial_count,
        "no": no_count,
        "error": error_count,
    }
    
    # Check if judge endpoint completely unreachable (zero verdicts for whole sub-question)
    use_judge = (
        _use_judge_coverage() and
        judge_verdicts and
        total_items > 0
    )
    
    fallback_reason = None
    if not _use_judge_coverage():
        fallback_reason = "judge disabled"
        use_judge = False
    elif not judge_verdicts or total_items == 0:
        fallback_reason = "judge unavailable (no verdicts)"
        use_judge = False
    else:
        error_rate = error_count / total_items if total_items > 0 else 1.0
        if error_rate > JUDGE_ERROR_THRESHOLD:
            use_judge = False
            fallback_reason = f"judge_error_rate_exceeded ({error_rate:.1%} > {JUDGE_ERROR_THRESHOLD:.0%})"
            logger.warning(f"Judge fallback triggered: {fallback_reason}")
    
    if not use_judge:
        if fallback:
            logger.warning(f"Falling back to tag-based coverage: {fallback_reason or 'judge disabled or unavailable'}")
            result = check_coverage(aspects, aspect_to_detail, original_details, digests, min_sources)
            result["judge_used"] = False
            result["judge_stats"] = judge_stats
            result["aspect_evidence"] = {}
            result["unjudged_aspects"] = []
            result["uncovered_reasons"] = {}
            if fallback_reason:
                result["fallback_reason"] = fallback_reason
            return result
        else:
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
                "fallback_reason": fallback_reason or "judge disabled",
            }

    # Judge-based coverage with explicit per-aspect states
    n_aspects = len(aspects)
    aspect_covered = [False] * n_aspects
    aspect_evidence = {}
    unjudged_aspects = []
    uncovered_reasons = {}
    
    # Build claim_hash -> verdict lookup for quick access
    verdict_lookup = {}
    for (asp_idx, src_id, claim_hash), verdict_data in judge_verdicts.items():
        verdict = verdict_data.get("verdict", {})
        if verdict.get("final") == "yes":
            verdict_lookup.setdefault(asp_idx, []).append((src_id, claim_hash, verdict))
    
    for i in range(n_aspects):
        covering = verdict_lookup.get(i, [])
        # Count distinct sources with "yes"
        yes_sources = set()
        evidence_list = []
        for src_id, claim_hash, verdict in covering:
            yes_sources.add(src_id)
            evidence_list.append({
                "source_id": src_id,
                "claim_prefix": verdict.get("reason", "")[:80] if verdict.get("reason") else "",
                "verdict": verdict.get("final"),
                "quote_supports_claim": verdict.get("quote_supports_claim"),
                "answers_aspect": verdict.get("answers_aspect"),
                "reason": verdict.get("reason"),
            })
        
        aspect_evidence[i] = evidence_list
        
        # Determine aspect state
        covered = len(covering) >= JUDGE_MIN_YES and len(yes_sources) >= MIN_COVER_SOURCES
        if covered:
            aspect_covered[i] = True
            logger.info(
                f"Aspect {i+1} covered_judge: yes={len(covering)} sources={len(yes_sources)} "
                f"evidence={evidence_list}"
            )
        else:
            # Check if aspect was judged but insufficient
            all_verdicts_for_aspect = [
                v for (asp_idx, _, _), v in judge_verdicts.items() 
                if asp_idx == i and v.get("verdict", {}).get("final") in ("yes", "partial", "no")
            ]
            error_verdicts = [
                v for (asp_idx, _, _), v in judge_verdicts.items() 
                if asp_idx == i and v.get("verdict", {}).get("final") == "error"
            ]
            missing_verdicts = n_aspects - len([
                v for (asp_idx, _, _), v in judge_verdicts.items() 
                if asp_idx == i
            ])
            
            if all_verdicts_for_aspect and not error_verdicts:
                # Judged but insufficient
                aspect_covered[i] = False
                uncovered_reasons[aspects[i]] = "judged_insufficient"
                logger.info(
                    f"Aspect {i+1} uncovered_judged: yes={len(covering)} (need {JUDGE_MIN_YES}) "
                    f"sources={len(yes_sources)} (need {MIN_COVER_SOURCES})"
                )
            elif error_verdicts or missing_verdicts > 0:
                # Unjudged (errors or missing)
                aspect_covered[i] = False
                unjudged_aspects.append(aspects[i])
                uncovered_reasons[aspects[i]] = "unjudged"
                logger.info(
                    f"Aspect {i+1} unjudged: errors={len(error_verdicts)} missing={missing_verdicts}"
                )
            else:
                # No candidates at all for this aspect
                aspect_covered[i] = False
                uncovered_reasons[aspects[i]] = "no_candidates"
                logger.info(f"Aspect {i+1} uncovered: no_candidates")
    
    # Determine uncovered aspects (only judged but insufficient)
    uncovered_aspects = [aspects[i] for i, covered in enumerate(aspect_covered) if not covered and aspects[i] not in unjudged_aspects]
    
    # Map uncovered aspects back to original details
    # A detail is uncovered if ANY of its aspects are either uncovered_judged OR unjudged
    n_details = len(original_details)
    detail_covered = [True] * n_details
    for i, covered in enumerate(aspect_covered):
        if not covered:
            detail_idx = aspect_to_detail[i]
            if detail_idx < n_details:
                detail_covered[detail_idx] = False
    
    uncovered_details = [original_details[i] for i, covered in enumerate(detail_covered) if not covered]
    
    sufficient = weighted_sources >= min_sources and not uncovered_details
    judge_used = len(unjudged_aspects) == 0
    
    return {
        "sufficient": sufficient,
        "source_count": len(by_source),
        "full_text_source_count": sum(1 for level in by_source.values() if level == "full_text"),
        "uncovered_details": uncovered_details,
        "uncovered_aspects": uncovered_aspects,
        "unjudged_aspects": unjudged_aspects,
        "uncovered_reasons": uncovered_reasons,
        "judge_used": judge_used,
        "judge_stats": judge_stats,
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