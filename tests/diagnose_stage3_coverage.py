#!/usr/bin/env python3
"""
TRACE Stage 3 Coverage Diagnostic Script
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent))

from apps.api.services.db_service import (
    get_papers_for_stage3,
    get_web_sources_for_stage3,
    supabase
)
from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder
from apps.api.agents.stage3_summarizer.chunk_selector import select_chunks, _split
from apps.api.agents.stage3_summarizer.quote_verifier import verify_quote


MATCHING_THRESHOLD = 0.6
QUOTE_FUZZY_THRESHOLD = 92
MIN_EVIDENCE_SCORE = 0.45


def read_coverage_results(query_id: str) -> List[Dict]:
    try:
        result = supabase.table("coverage_results").select("*").eq("query_id", query_id).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to read coverage_results for query {query_id}: {e}")
        return []


def read_digests(query_id: str) -> List[Dict]:
    try:
        result = supabase.table("digests").select("*").eq("query_id", query_id).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to read digests for query {query_id}: {e}")
        return []


def read_sub_questions(query_id: str) -> List[Dict]:
    try:
        result = supabase.table("sub_questions").select("*").eq("query_id", query_id).execute()
        return result.data or []
    except Exception as e:
        logger.error(f"Failed to read sub_questions for query {query_id}: {e}")
        return []


def get_latest_query_id() -> Optional[str]:
    try:
        result = supabase.table("digests").select("query_id").order("created_at", desc=True).limit(1).execute()
        if result.data and result.data[0].get("query_id"):
            return result.data[0]["query_id"]
        return None
    except Exception as e:
        logger.error(f"Failed to get latest query_id: {e}")
        return None


def clean_topic_for_prefix(main_topic: str) -> str:
    """Strip leading 'What is' and trailing '?' from main topic for prefixing."""
    t = main_topic.strip()
    t = re.sub(r'^what\s+is\s+', '', t, flags=re.IGNORECASE)
    t = re.sub(r'\?$', '', t).strip()
    return t


def build_topic_prefixed(main_topic: str, detail: str) -> str:
    """Build topic-prefixed detail question."""
    cleaned_topic = clean_topic_for_prefix(main_topic)
    return f"{cleaned_topic}: {detail}"


def get_full_text_sources_for_subquestion(digests: List[Dict], all_papers: List[Dict]) -> List[Dict]:
    sources = []
    for digest in digests:
        source_id = digest.get("source_id")
        evidence_level = digest.get("evidence_level", "full_text")
        paper = None
        for p in all_papers:
            if p.get("id") == source_id:
                paper = p
                break
        if paper:
            full_text = paper.get("full_text", "")
            if full_text:
                sources.append({
                    "source_id": source_id,
                    "full_text": full_text,
                    "evidence_level": evidence_level,
                    "paper": paper
                })
    return sources


def collect_all_findings(digests: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Extract all findings from digests, split into verified and unverified."""
    all_findings = []
    for d in digests:
        source_id = d.get("source_id")
        evidence_level = d.get("evidence_level", "full_text")
        for f in d.get("findings", []):
            if "claim" in f:
                f_copy = f.copy()
                f_copy["source_id"] = source_id
                f_copy["evidence_level"] = evidence_level
                all_findings.append(f_copy)
    
    verified = [f for f in all_findings if f.get("verified", False)]
    unverified = [f for f in all_findings if not f.get("verified", False)]
    return verified, unverified


def print_data_loading(sub_id: str, main_topic: str, detail_questions: List[str],
                       digests: List[Dict], verified_findings: List[Dict],
                       unverified_findings: List[Dict],
                       full_text_sources: List[Dict]) -> None:
    """Print DATA LOADING summary for a sub-question."""
    print(f"\n{'='*70}")
    print(f"DATA LOADING for sub-question: {sub_id}")
    print(f"{'='*70}")
    print(f"  Main topic (raw): '{main_topic}'")
    print(f"  Main topic (cleaned for prefix): '{clean_topic_for_prefix(main_topic)}'")
    print(f"  Detail questions ({len(detail_questions)}):")
    for i, dq in enumerate(detail_questions):
        print(f"    {i+1}. {dq}")
    
    print(f"\n  Digests rows: {len(digests)}")
    print(f"  Total findings: {len(verified_findings) + len(unverified_findings)}")
    print(f"    Verified: {len(verified_findings)}")
    print(f"    Unverified: {len(unverified_findings)}")
    
    if not verified_findings and not unverified_findings:
        print("  DATA MISSING: no findings in digests")
    
    print(f"\n  Sources with parsed full text: {len(full_text_sources)}")
    for src in full_text_sources:
        ft_len = len(src.get("full_text", ""))
        print(f"    - source_id={src['source_id']} evidence_level={src.get('evidence_level')} full_text_chars={ft_len}")
        
        # Count chunks using same chunking as chunk_selector.py
        ft = src.get("full_text", "")
        chunks = _split(ft)
        filtered = [c for c in chunks if not any(sw in c.lower() for sw in ["reference", "bibliograph", "acknowledg", "appendix", "funding", "conflict"])]
        print(f"      chunks after split: {len(chunks)}, after filter: {len(filtered)}")
    
    if not full_text_sources:
        print("  DATA MISSING: no full text sources")


def check_cause_a(detail: str, main_topic: str, verified_findings: List[Dict], threshold: float) -> Dict:
    """Check for matching problem."""
    logger.info(f"  Checking cause A for detail: '{detail}'")
    
    if not verified_findings:
        return {"state": "UNKNOWN", "reason": "no verified findings with 'claim' key"}
    
    embedder = get_embedder()
    raw_detail = detail
    prefixed_detail = build_topic_prefixed(main_topic, detail)
    
    claims = [f["claim"] for f in verified_findings]
    detail_raw_emb = embedder.encode([raw_detail], normalize_embeddings=True)[0]
    detail_prefixed_emb = embedder.encode([prefixed_detail], normalize_embeddings=True)[0]
    claim_embs = embedder.encode(claims, normalize_embeddings=True)
    
    raw_sims = claim_embs @ detail_raw_emb
    prefixed_sims = claim_embs @ detail_prefixed_emb
    
    best_raw_idx = max(range(len(raw_sims)), key=lambda i: raw_sims[i])
    best_prefixed_idx = max(range(len(prefixed_sims)), key=lambda i: prefixed_sims[i])
    
    best_raw_score = float(raw_sims[best_raw_idx])
    best_prefixed_score = float(prefixed_sims[best_prefixed_idx])
    
    best_finding = verified_findings[best_raw_idx]
    
    applies = (best_raw_score < threshold and 
               (best_prefixed_score >= threshold or abs(best_prefixed_score - best_raw_score) <= 0.05))
    
    state = "APPLIES" if applies else "DOES NOT APPLY"
    reason = f"raw={best_raw_score:.3f}, prefixed={best_prefixed_score:.3f}, threshold={threshold}"
    
    return {
        "state": state,
        "reason": reason,
        "best_verified_finding": {
            "claim": best_finding.get("claim", ""),
            "verified": True,
            "source_id": best_finding.get("source_id"),
            "score_raw": best_raw_score,
            "score_prefixed": best_prefixed_score
        },
        "threshold": threshold,
        "best_raw_score": best_raw_score,
        "best_prefixed_score": best_prefixed_score
    }


def check_cause_b(detail: str, main_topic: str, 
                  chunks_selected: List[Tuple[int, str]],
                  all_full_text_sources: List[Dict]) -> Dict:
    """Check for selection problem."""
    logger.info(f"  Checking cause B for detail: '{detail}'")
    
    if not all_full_text_sources:
        return {"state": "UNKNOWN", "reason": "no full text sources"}
    
    embedder = get_embedder()
    
    all_chunks = []
    chunk_metadata = []
    
    for source in all_full_text_sources:
        full_text = source.get("full_text", "")
        if not full_text:
            continue
        source_chunks = _split(full_text)
        filtered_chunks = [c for c in source_chunks if not any(sw in c.lower() for sw in ["reference", "bibliograph", "acknowledg", "appendix", "funding", "conflict"])]
        all_chunks.extend(filtered_chunks)
        chunk_metadata.extend([(source, i) for i in range(len(filtered_chunks))])
    
    if not all_chunks:
        return {"state": "UNKNOWN", "reason": "no chunks after filtering"}
    
    detail_emb = embedder.encode([detail], normalize_embeddings=True)[0]
    chunk_embs = embedder.encode(all_chunks, normalize_embeddings=True)
    detail_chunk_sims = chunk_embs @ detail_emb
    
    best_detail_chunk_idx = max(range(len(detail_chunk_sims)), key=lambda i: detail_chunk_sims[i])
    best_detail_score = float(detail_chunk_sims[best_detail_chunk_idx])
    best_detail_chunk_text = all_chunks[best_detail_chunk_idx]
    best_detail_source, _ = chunk_metadata[best_detail_chunk_idx]
    
    is_selected = False
    for _, chunk_text in chunks_selected:
        if chunk_text.strip() == best_detail_chunk_text.strip():
            is_selected = True
            break
    
    sub_chunks = [text for _, text in chunks_selected]
    if not sub_chunks:
        return {"state": "UNKNOWN", "reason": "no chunks selected for sub-question"}
    
    sub_chunk_embs = embedder.encode(sub_chunks, normalize_embeddings=True)
    sub_detail_emb = embedder.encode([main_topic], normalize_embeddings=True)
    sub_chunk_sims = (sub_chunk_embs @ sub_detail_emb.T).flatten()
    best_sub_chunk_idx = max(range(len(sub_chunk_sims)), key=lambda i: sub_chunk_sims[i])
    best_sub_chunk_score = float(sub_chunk_sims[best_sub_chunk_idx])
    
    applies = (not is_selected and best_detail_score > best_sub_chunk_score * 1.5)
    state = "APPLIES" if applies else "DOES NOT APPLY"
    
    return {
        "state": state,
        "reason": f"best_detail={best_detail_score:.3f}, best_sub_chunk={best_sub_chunk_score:.3f}, is_selected={is_selected}",
        "best_detail_score": best_detail_score,
        "best_sub_chunk_score": best_sub_chunk_score,
        "best_detail_chunk_text": best_detail_chunk_text[:200] + "..." if len(best_detail_chunk_text) > 200 else best_detail_chunk_text,
        "is_selected": is_selected,
        "detail_source_id": best_detail_source.get("id") if best_detail_source else None
    }


def check_cause_c(detail: str, unverified_findings: List[Dict], threshold: float) -> Dict:
    """Check for verification loss."""
    logger.info(f"  Checking cause C for detail: '{detail}'")
    
    if not unverified_findings:
        return {"state": "UNKNOWN", "reason": "no unverified findings with 'claim' key"}
    
    embedder = get_embedder()
    detail_emb = embedder.encode([detail], normalize_embeddings=True)[0]
    claim_embs = embedder.encode([f["claim"] for f in unverified_findings], normalize_embeddings=True)
    detail_claim_sims = claim_embs @ detail_emb
    
    top_unverified_indices = sorted(range(len(detail_claim_sims)), 
                                   key=lambda i: detail_claim_sims[i], 
                                   reverse=True)[:3]
    
    any_above_threshold = any(detail_claim_sims[i] >= threshold for i in top_unverified_indices)
    
    top_unverified_details = []
    for idx in top_unverified_indices:
        f = unverified_findings[idx]
        top_unverified_details.append({
            "claim": f.get("claim", ""),
            "quote": f.get("quote", ""),
            "verified": f.get("verified", False),
            "score": float(detail_claim_sims[idx]),
            "source_id": f.get("source_id")
        })
    
    state = "APPLIES" if any_above_threshold else "DOES NOT APPLY"
    reason = f"top_unverified_score={max(detail_claim_sims):.3f}, threshold={threshold}"
    
    return {
        "state": state,
        "reason": reason,
        "unverified_count": len(unverified_findings),
        "top_unverified_findings": top_unverified_details,
        "any_above_threshold": any_above_threshold,
        "threshold": threshold
    }


def check_cause_d(detail: str, all_chunks: List[str], 
                  best_overall_score: float, min_score: float,
                  a_state: str, b_state: str, c_state: str) -> Dict:
    """Check for evidence missing. Applies when A,B,C are not APPLIES and data exists."""
    logger.info(f"  Checking cause D for detail: '{detail}'")
    
    data_present = len(all_chunks) > 0
    a_not_applies = a_state != "APPLIES"
    b_not_applies = b_state != "APPLIES"
    c_not_applies = c_state != "APPLIES"
    
    applies = data_present and a_not_applies and b_not_applies and c_not_applies and best_overall_score < min_score
    
    if not data_present:
        state = "UNKNOWN"
        reason = "no chunks available"
    elif not (a_not_applies and b_not_applies and c_not_applies):
        state = "DOES NOT APPLY"
        reason = "another cause already applies"
    else:
        state = "APPLIES" if applies else "DOES NOT APPLY"
        reason = f"best_score={best_overall_score:.3f}, min_score={min_score}"
    
    return {
        "state": state,
        "reason": reason,
        "best_overall_score": float(best_overall_score),
        "min_score": min_score,
        "total_chunks": len(all_chunks)
    }


def print_detail_report(detail: str, main_topic: str,
                        cause_a: Dict, cause_b: Dict, cause_c: Dict, cause_d: Dict,
                        verified_findings: List[Dict], unverified_findings: List[Dict],
                        chunks_selected: List[Tuple[int, str]]) -> List[str]:
    """Print per-detail report with all raw numbers."""
    print(f"\n{'='*70}")
    print(f"DETAIL: '{detail}'")
    print(f"{'='*70}")
    
    causes = {"A": cause_a, "B": cause_b, "C": cause_c, "D": cause_d}
    applicable = [c for c in ["A", "B", "C", "D"] if causes[c]["state"] == "APPLIES"]
    print(f"APPLICABLE CAUSES: {applicable if applicable else '(none)'}")
    
    # CAUSE A
    ca = cause_a
    print(f"\nCAUSE A (threshold={ca.get('threshold', MATCHING_THRESHOLD):.2f}): {ca['state']} - {ca['reason']}")
    print(f"  Top 3 verified findings by similarity to detail (raw / prefixed):")
    # Re-compute for all verified findings to show top 3
    embedder = get_embedder()
    raw_detail = detail
    prefixed_detail = build_topic_prefixed(main_topic, detail)
    if verified_findings:
        claims = [f["claim"] for f in verified_findings]
        raw_sims = (embedder.encode(claims, normalize_embeddings=True) @ embedder.encode([raw_detail], normalize_embeddings=True)[0])
        pref_sims = (embedder.encode(claims, normalize_embeddings=True) @ embedder.encode([prefixed_detail], normalize_embeddings=True)[0])
        top3 = sorted(range(len(raw_sims)), key=lambda i: raw_sims[i], reverse=True)[:3]
        for i, idx in enumerate(top3):
            f = verified_findings[idx]
            claim_text = f['claim'][:80].replace('\u2011', '-').replace('\u2013', '-').replace('\u2014', '-')
            print(f"    {i+1}. raw={raw_sims[idx]:.3f} pref={pref_sims[idx]:.3f} verified=True source={f.get('source_id')} claim='{claim_text}...'")
    else:
        print("    (no verified findings)")
    
    # CAUSE B
    cb = cause_b
    print(f"\nCAUSE B: {cb['state']} - {cb['reason']}")
    print(f"  Best chunk for detail: score={cb.get('best_detail_score', 0):.3f}")
    print(f"  Best sub-question chunk: score={cb.get('best_sub_chunk_score', 0):.3f}")
    chunk_text = cb.get('best_detail_chunk_text', 'N/A')[:150].replace('\u2011', '-').replace('\u2013', '-').replace('\u2014', '-')
    print(f"  Best detail chunk excerpt: {chunk_text}...")
    print(f"  Was selected by chunk_selector? {cb.get('is_selected', False)}")
    
    # CAUSE C
    cc = cause_c
    print(f"\nCAUSE C (threshold={cc.get('threshold', MATCHING_THRESHOLD):.2f}): {cc['state']} - {cc['reason']}")
    print(f"  Total unverified findings: {cc.get('unverified_count', 0)}")
    for i, f in enumerate(cc.get('top_unverified_findings', [])[:3]):
        claim_text = f['claim'][:80].replace('\u2011', '-').replace('\u2013', '-').replace('\u2014', '-')
        quote_text = f.get('quote', '')[:60].replace('\u2011', '-').replace('\u2013', '-').replace('\u2014', '-')
        print(f"    {i+1}. score={f['score']:.3f} source={f.get('source_id')} claim='{claim_text}...' quote='{quote_text}...'")
    
    # CAUSE D
    cd = cause_d
    print(f"\nCAUSE D (min_score={cd.get('min_score', MIN_EVIDENCE_SCORE):.2f}): {cd['state']} - {cd['reason']}")
    print(f"  Best evidence score: {cd.get('best_overall_score', 0):.3f}")
    print(f"  Total chunks: {cd.get('total_chunks', 0)}")
    
    return applicable


def diagnose_query(query_id: str, sub_question_id: Optional[str] = None, 
                   min_evidence_score: float = MIN_EVIDENCE_SCORE) -> Dict:
    logger.info(f"Starting diagnosis for query_id: {query_id}, sub_question_id: {sub_question_id}")
    
    coverage_results = read_coverage_results(query_id)
    digests = read_digests(query_id)
    sub_questions = read_sub_questions(query_id)
    
    if not coverage_results:
        logger.warning(f"No coverage_results found for query_id {query_id}")
        return {}
    
    if sub_question_id:
        coverage_results = [cr for cr in coverage_results if cr.get("sub_question_id") == sub_question_id]
        if not coverage_results:
            logger.warning(f"No coverage_results found for sub_question_id {sub_question_id}")
            return {}
    
    all_papers = []
    sub_question_map = {}
    
    for sub_q in sub_questions:
        papers = get_papers_for_stage3(query_id, sub_q["id"])
        all_papers.extend(papers)
        sub_question_map[sub_q["id"]] = sub_q
    
    sub_question_coverage_map = {}
    for coverage in coverage_results:
        sub_id = coverage.get("sub_question_id")
        if sub_id not in sub_question_coverage_map:
            sub_question_coverage_map[sub_id] = []
        sub_question_coverage_map[sub_id].append(coverage)
    
    diagnosis_results = {}
    detail_counter = 0
    
    for sub_id, coverages in sub_question_coverage_map.items():
        for coverage in coverages:
            if coverage.get("sufficient", True):
                continue
                
            sub_q = sub_question_map.get(sub_id)
            if not sub_q:
                logger.warning(f"Sub-question {sub_id} not found in sub_questions table")
                continue
            
            # Check ID matching
            coverage_sqid = coverage.get("sub_question_id")
            digests_for_sq = [d for d in digests if d.get("sub_question_id") == sub_id]
            print(f"\nID MATCH CHECK: coverage.sub_question_id={coverage_sqid} sub_q.id={sub_id} digests_found={len(digests_for_sq)}")
            if coverage_sqid != sub_id:
                print(f"  WARNING: ID mismatch between coverage ({coverage_sqid}) and sub_question ({sub_id})")
            
            sub_digests = digests_for_sq
            full_text_sources = get_full_text_sources_for_subquestion(sub_digests, all_papers)
            
            main_topic = sub_q.get("main_topic", "")
            detail_questions = sub_q.get("detail_questions", [])
            
            verified_findings, unverified_findings = collect_all_findings(sub_digests)
            
            # Build chunks_selected for this sub-question
            chunks_selected = []
            for source in full_text_sources:
                full_text = source["full_text"]
                if full_text:
                    chunks = _split(full_text)
                    filtered_chunks = [c for c in chunks if not any(sw in c.lower() for sw in ["reference", "bibliograph", "acknowledg", "appendix", "funding", "conflict"])]
                    if filtered_chunks:
                        selected = select_chunks(main_topic, filtered_chunks, top_k=5)
                        chunks_selected.extend(selected)
            
            # Print DATA LOADING summary
            print_data_loading(sub_id, main_topic, detail_questions,
                              sub_digests, verified_findings, unverified_findings, full_text_sources)
            
            # Process each uncovered detail
            for detail in coverage.get("uncovered_details", []):
                detail_counter += 1
                
                cause_a = check_cause_a(detail, main_topic, verified_findings, MATCHING_THRESHOLD)
                cause_b = check_cause_b(detail, main_topic, chunks_selected, full_text_sources)
                cause_c = check_cause_c(detail, unverified_findings, MATCHING_THRESHOLD)
                
                # Compute best overall score for cause D
                embedder = get_embedder()
                detail_emb = embedder.encode([detail], normalize_embeddings=True)[0]
                
                all_chunks = []
                for source in full_text_sources:
                    full_text = source["full_text"]
                    if full_text:
                        all_chunks.extend(_split(full_text))
                filtered_chunks = [c for c in all_chunks if not any(sw in c.lower() for sw in ["reference", "bibliograph", "acknowledg", "appendix", "funding", "conflict"])]
                
                if filtered_chunks:
                    chunk_embs = embedder.encode(filtered_chunks, normalize_embeddings=True)
                    best_overall_score = (chunk_embs @ detail_emb).max().item()
                else:
                    best_overall_score = 0.0
                
                cause_d = check_cause_d(detail, filtered_chunks, best_overall_score, min_evidence_score,
                                       cause_a["state"], cause_b["state"], cause_c["state"])
                
                # Print full detail report
                applicable = print_detail_report(detail, main_topic,
                                                cause_a, cause_b, cause_c, cause_d,
                                                verified_findings, unverified_findings,
                                                chunks_selected)
                
                detail_diagnosis = {
                    "detail": detail,
                    "cause_a": cause_a,
                    "cause_b": cause_b,
                    "cause_c": cause_c,
                    "cause_d": cause_d,
                    "applicable_causes": applicable,
                    "main_topic": main_topic,
                    "sub_question_id": sub_id,
                }
                
                if sub_id not in diagnosis_results:
                    diagnosis_results[sub_id] = []
                diagnosis_results[sub_id].append(detail_diagnosis)
    
    # Store total count for summary
    diagnosis_results["_total_details_analyzed"] = detail_counter
    return diagnosis_results


def print_summary(diagnosis_results: Dict) -> None:
    print(f"\n{'='*70}")
    print("DIAGNOSTIC SUMMARY")
    print(f"{'='*70}")
    
    cause_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    total_analyzed = diagnosis_results.get("_total_details_analyzed", 0)
    
    for sub_q_id, details in diagnosis_results.items():
        if sub_q_id == "_total_details_analyzed":
            continue
        for detail in details:
            for cause in detail.get("applicable_causes", []):
                cause_counts[cause] += 1
    
    print(f"Total uncovered details analyzed: {total_analyzed}")
    for cause in ["A", "B", "C", "D"]:
        count = cause_counts[cause]
        percentage = (count / total_analyzed * 100) if total_analyzed > 0 else 0
        print(f"  Cause {cause}: {count} details ({percentage:.1f}%)")
        
        if cause == "A":
            print(f"    Recommendation: embed details with the topic prefix / have the digest generator tag findings with the detail they answer")
        elif cause == "B":
            print(f"    Recommendation: add 1-2 detail-targeted chunks per detail to chunk selection")
        elif cause == "C":
            print(f"    Recommendation: inspect quote verifier threshold/normalization")
        elif cause == "D":
            print(f"    Recommendation: escalate to next-ranked papers, then new queries (Loop 2)")


def main():
    parser = argparse.ArgumentParser(description="TRACE Stage 3 Coverage Diagnostic Script")
    parser.add_argument("--query-id", help="Query ID to diagnose (default: latest query)")
    parser.add_argument("--sub-question-id", help="Specific sub-question ID to analyze (default: all with insufficient coverage)")
    parser.add_argument("--out", default="reports/stage3_diagnosis.json", help="Output file path (default: reports/stage3_diagnosis.json)")
    parser.add_argument("--min-evidence-score", type=float, default=MIN_EVIDENCE_SCORE, help=f"Minimum evidence score for cause D (default: {MIN_EVIDENCE_SCORE})")
    
    args = parser.parse_args()
    
    query_id = args.query_id
    if not query_id:
        query_id = get_latest_query_id()
        if not query_id:
            print("ERROR: No query_id provided and could not find latest query_id")
            sys.exit(1)
    
    print(f"Running Stage 3 diagnostic for query_id: {query_id}")
    if args.sub_question_id:
        print(f"Filtering by sub_question_id: {args.sub_question_id}")
    
    diagnosis_results = diagnose_query(query_id, args.sub_question_id, args.min_evidence_score)
    
    if not diagnosis_results:
        print("No diagnosis results generated")
        return
    
    print_summary(diagnosis_results)
    
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Remove internal counter before saving
    save_results = {k: v for k, v in diagnosis_results.items() if k != "_total_details_analyzed"}
    
    with open(output_path, 'w') as f:
        json.dump(save_results, f, indent=2, default=str)
    
    print(f"\nDiagnosis results written to: {output_path}")
    
    print("\nRECOMMENDATIONS PER CAUSE:")
    print("A -> embed details with the topic prefix / have the digest generator tag findings with the detail they answer")
    print("B -> add 1-2 detail-targeted chunks per detail to chunk selection")
    print("C -> inspect quote verifier threshold/normalization")
    print("D -> escalate to next-ranked papers, then new queries (Loop 2)")


if __name__ == "__main__":
    main()