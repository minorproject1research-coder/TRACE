from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder
import logging
from typing import List, Dict, Any, Set

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