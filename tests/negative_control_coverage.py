#!/usr/bin/env python3
"""
Script 2: Negative control for Stage 3 coverage.

Runs the REAL pipeline functions (chunk selection, digest generation, quote verification, coverage check)
with an added control detail that the retrieved papers should NOT be able to answer.

  python tests/negative_control_coverage.py --query-id <id> [--sub-question-id <id>] [--controls-file controls.json]
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --- Constants ---
DEFAULT_CONTROLS = [
    "What are the legal and regulatory requirements for {topic}?",
    "What is the history of {topic} before 2000?",
    "How much does {topic} cost to deploy in cloud pricing terms?",
]
MAX_LLM_CALLS_DEFAULT = 40

# Setup
sys.path.insert(0, str(Path(__file__).parent.parent))

from apps.api.services.db_service import (
    get_papers_for_stage3,
    get_web_sources_for_stage3,
    supabase,
)
from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder
from apps.api.agents.stage3_summarizer import (
    chunk_selector, 
    digest_generator, 
    quote_verifier, 
    coverage_check,
    detail_aspects,
    evidence_judge,
)
from apps.api.agents.stage3_summarizer.chunk_selector import _clean_topic
from apps.api.agents.stage3_summarizer.coverage_check import MIN_TAG_SIM, EVIDENCE_WEIGHT

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_controls(controls_file: Optional[str]) -> List[str]:
    """Load control templates from file or use defaults."""
    if controls_file:
        with open(controls_file, "r") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return data.get("controls", DEFAULT_CONTROLS)
    return DEFAULT_CONTROLS


def load_stored_coverage(query_id: str, sub_question_id: str) -> Optional[Dict]:
    """Load the stored coverage result for comparison."""
    result = supabase.table("coverage_results").select("*").eq("query_id", query_id).eq("sub_question_id", sub_question_id).execute()
    if result.data:
        return result.data[0]
    return None


def load_sub_question(query_id: str, sub_question_id: str) -> Optional[Dict]:
    """Load sub-question from DB."""
    result = supabase.table("sub_questions").select("*").eq("query_id", query_id).eq("id", sub_question_id).execute()
    if result.data:
        return result.data[0]
    return None


def build_jobs_for_subquestion(
    query_id: str,
    sq: Dict,
    max_papers: int = 3,
    max_web: int = 2,
) -> List[Dict]:
    """Build jobs exactly like the orchestrator does."""
    jobs = []
    cleaned_topic = _clean_topic(sq["main_topic"])
    original_details = sq["detail_questions"]
    
    # Split details into aspects (with near-duplicate merging)
    aspects, aspect_to_detail = detail_aspects.flatten_aspects(
        original_details, sq["id"], cleaned_topic
    )
    
    papers = get_papers_for_stage3(query_id, sq["id"])
    for p in papers[:max_papers]:
        chunks = chunk_selector.build_chunks(p)
        selected = chunk_selector.select_chunks(
            sq["main_topic"],
            chunks,
            detail_questions=aspects,
            main_topic=cleaned_topic,
        )
        level = "full_text" if p.get("has_full_text") else "abstract"
        jobs.append({
            "source_type": "paper",
            "source": p,
            "selected": selected,
            "weight": p.get("combined_score"),
            "evidence_level": level,
            "aspects": aspects,
            "aspect_to_detail": aspect_to_detail,
            "original_details": original_details,
        })
    
    web_sources = get_web_sources_for_stage3(sq["id"])
    for w in web_sources[:max_web]:
        snippet = w.get("snippet") or ""
        if len(snippet) >= 200:
            jobs.append({
                "source_type": "web",
                "source": w,
                "selected": [(0, snippet)],
                "weight": w.get("reliability_score"),
                "evidence_level": "web_snippet",
                "aspects": aspects,
                "aspect_to_detail": aspect_to_detail,
                "original_details": original_details,
            })
    
    return jobs


def run_digest_jobs(
    jobs: List[Dict],
    sub_question: str,
    detail_questions: List[str],
    cleaned_topic: str,
    llm_call_counter: List[int],
    max_llm_calls: int,
) -> List[List[Dict]]:
    """Run digest generation for all jobs, counting LLM calls."""
    findings_per_job = []
    for job in jobs:
        if llm_call_counter[0] >= max_llm_calls:
            logger.warning(f"Max LLM calls ({max_llm_calls}) reached, stopping")
            findings_per_job.append([])
            continue
        
        selected = job["selected"]
        if not selected:
            findings_per_job.append([])
            continue
        
        # Use aspects from job for digest generation
        aspects = job.get("aspects", detail_questions)
        
        findings = digest_generator.generate_digest(
            sub_question,
            selected,
            detail_aspects=aspects,
            main_topic=cleaned_topic,
        )
        findings_per_job.append(findings)
        llm_call_counter[0] += 1
        logger.info(f"  LLM call #{llm_call_counter[0]} for {job['source_type']} source {job['source'].get('id', 'unknown')}")
    
    return findings_per_job


def run_coverage_check(
    aspects: List[str],
    aspect_to_detail: List[int],
    original_details: List[str],
    digests: List[Dict],
    judge_verdicts: Dict = None,
) -> Dict:
    """Run coverage_check with the modified detail list."""
    # Convert digests to the format expected by coverage_check
    rows = []
    for d in digests:
        rows.append({
            "source_id": d["source_id"],
            "evidence_level": d.get("evidence_level", "full_text"),
            "findings": d["findings"],
        })
    return coverage_check.check_coverage_judged(
        aspects, aspect_to_detail, original_details, rows, judge_verdicts or {}
    )


def run_negative_control(
    query_id: str,
    sub_question_id: str,
    control_template: str,
    max_llm_calls: int,
) -> Dict:
    """Run a single negative control for a sub-question."""
    # Load sub-question
    sq = load_sub_question(query_id, sub_question_id)
    if not sq:
        return {"error": f"Sub-question {sub_question_id} not found"}
    
    # Load stored coverage for comparison
    stored_cov = load_stored_coverage(query_id, sub_question_id)
    
    main_topic = sq["main_topic"]
    cleaned_topic = _clean_topic(main_topic)
    original_details = sq["detail_questions"]
    
    # Get base aspects and mapping (without control)
    base_aspects, base_aspect_to_detail = detail_aspects.flatten_aspects(
        original_details, sq["id"], cleaned_topic
    )
    
    # Build control detail
    control_detail = control_template.format(topic=cleaned_topic)
    modified_details = original_details + [control_detail]
    control_idx = len(modified_details) - 1  # 0-indexed
    
    # Get aspects for modified details (with control)
    modified_aspects, modified_aspect_to_detail = detail_aspects.flatten_aspects(
        modified_details, sq["id"], cleaned_topic
    )
    
    logger.info(f"Running control for sub-question {sub_question_id}")
    logger.info(f"  Main topic: {main_topic}")
    logger.info(f"  Original details: {len(original_details)} -> {len(base_aspects)} aspects")
    logger.info(f"  Control detail: {control_detail}")
    logger.info(f"  Modified details: {len(modified_details)} -> {len(modified_aspects)} aspects")
    
    # Build jobs using modified aspects (including control)
    jobs = []
    for p in get_papers_for_stage3(query_id, sq["id"])[:3]:
        chunks = chunk_selector.build_chunks(p)
        selected = chunk_selector.select_chunks(
            sq["main_topic"],
            chunks,
            detail_questions=modified_aspects,
            main_topic=cleaned_topic,
        )
        level = "full_text" if p.get("has_full_text") else "abstract"
        jobs.append({
            "source_type": "paper",
            "source": p,
            "selected": selected,
            "weight": p.get("combined_score"),
            "evidence_level": level,
            "aspects": modified_aspects,
            "aspect_to_detail": modified_aspect_to_detail,
            "original_details": modified_details,
        })
    
    for w in get_web_sources_for_stage3(sq["id"])[:2]:
        snippet = w.get("snippet") or ""
        if len(snippet) >= 200:
            jobs.append({
                "source_type": "web",
                "source": w,
                "selected": [(0, snippet)],
                "weight": w.get("reliability_score"),
                "evidence_level": "web_snippet",
                "aspects": modified_aspects,
                "aspect_to_detail": modified_aspect_to_detail,
                "original_details": modified_details,
            })
    
    logger.info(f"  Built {len(jobs)} jobs ({sum(1 for j in jobs if j['source_type']=='paper')} papers, {sum(1 for j in jobs if j['source_type']=='web')} web)")
    
    # Run digest generation
    llm_calls = [0]
    findings_per_job = run_digest_jobs(
        jobs, sq["main_topic"], modified_details, cleaned_topic,
        llm_calls, max_llm_calls
    )
    
    # Assemble digests
    digests = []
    for job, findings in zip(jobs, findings_per_job):
        digests.append({
            "source_id": str(job["source"].get("id")),
            "evidence_level": job["evidence_level"],
            "findings": findings,
        })
    
    # Build chunk_lookup for judge
    chunk_lookup = {}
    for job in jobs:
        for chunk_id, chunk_text in job["selected"]:
            chunk_lookup[str(chunk_id)] = chunk_text
    
    # Run judge for modified aspects
    judge_verdicts = {}
    has_verified = any(f.get("verified") for d in digests for f in d.get("findings", []))
    if has_verified and modified_aspects:
        candidates, judge_verdicts = evidence_judge.run_judge_for_subquestion(
            modified_aspects, digests, chunk_lookup
        )
    
    # Run coverage check with MODIFIED details (including control) using judge
    coverage = run_coverage_check(
        modified_aspects, modified_aspect_to_detail, modified_details, digests, judge_verdicts
    )
    
    # Also run with ORIGINAL details for comparison (using base aspects, no judge)
    original_digests = []
    for job, findings in zip(jobs, findings_per_job):
        original_digests.append({
            "source_id": str(job["source"].get("id")),
            "evidence_level": job["evidence_level"],
            "findings": findings,
        })
    original_coverage = run_coverage_check(
        base_aspects, base_aspect_to_detail, original_details, original_digests, {}
    )
    
    # Check if control detail was covered
    control_covered = control_detail not in coverage.get("uncovered_details", [])
    control_uncovered = control_detail in coverage.get("uncovered_details", [])
    
    # Find any findings tagged with the control detail
    tagged_control_findings = []
    for d in digests:
        for f in d.get("findings", []):
            answers = f.get("answers_details", [])
            if (control_idx + 1) in answers:
                model = get_embedder()
                claim = f.get("claim", "")
                if claim:
                    c_emb = model.encode([control_detail], normalize_embeddings=True)[0]
                    f_emb = model.encode([claim], normalize_embeddings=True)[0]
                    sim = float(c_emb @ f_emb)
                else:
                    sim = None
                tagged_control_findings.append({
                    "source_id": d["source_id"],
                    "claim": claim,
                    "verified": f.get("verified", False),
                    "similarity": sim,
                    "answers_details": answers,
                })
    
    # Check if original details' coverage changed
    original_uncovered = set(stored_cov.get("uncovered_details", [])) if stored_cov else set()
    new_uncovered = set(coverage.get("uncovered_details", []))
    new_uncovered_orig = {d for d in new_uncovered if d in original_details}
    original_changed = original_uncovered != new_uncovered_orig
    
    result = {
        "sub_question_id": sub_question_id,
        "main_topic": main_topic,
        "cleaned_topic": cleaned_topic,
        "control_detail": control_detail,
        "control_idx": control_idx + 1,
        "control_covered": control_covered,
        "control_uncovered": control_uncovered,
        "tagged_control_findings": tagged_control_findings,
        "original_coverage_changed": original_changed,
        "stored_uncovered": list(original_uncovered),
        "new_uncovered_original": list(new_uncovered_orig),
        "coverage_sufficient": coverage.get("sufficient"),
        "judge_used": coverage.get("judge_used"),
        "judge_stats": coverage.get("judge_stats"),
        "fallback_reason": coverage.get("fallback_reason"),
        "llm_calls_used": llm_calls[0],
    }
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Negative control for Stage 3 coverage")
    parser.add_argument("--query-id", required=True, help="Query ID to test")
    parser.add_argument("--sub-question-id", help="Specific sub-question ID (default: all in query)")
    parser.add_argument("--controls-file", help="JSON file with control templates")
    parser.add_argument("--max-llm-calls", type=int, default=MAX_LLM_CALLS_DEFAULT, help=f"Max Groq calls (default: {MAX_LLM_CALLS_DEFAULT})")
    
    args = parser.parse_args()
    
    query_id = args.query_id
    controls = load_controls(args.controls_file)
    
    # Get sub-questions for this query
    if args.sub_question_id:
        sub_question_ids = [args.sub_question_id]
    else:
        result = supabase.table("sub_questions").select("id").eq("query_id", query_id).execute()
        sub_question_ids = [r["id"] for r in result.data]
    
    if not sub_question_ids:
        logger.error(f"No sub-questions found for query {query_id}")
        sys.exit(1)
    
    logger.info(f"Running negative controls for query {query_id}")
    logger.info(f"Sub-questions: {sub_question_ids}")
    logger.info(f"Controls: {len(controls)} templates")
    logger.info(f"Max LLM calls: {args.max_llm_calls}")
    
    all_results = []
    total_llm_calls = 0
    any_fail = False
    
    for sq_id in sub_question_ids:
        for control_template in controls:
            if total_llm_calls >= args.max_llm_calls:
                logger.warning(f"Max LLM calls ({args.max_llm_calls}) reached, stopping")
                break
            
            result = run_negative_control(query_id, sq_id, control_template, args.max_llm_calls - total_llm_calls)
            total_llm_calls += result.get("llm_calls_used", 0)
            all_results.append(result)
            
            # Print result
            control = result.get("control_detail", "N/A")
            verdict = "PASS" if result.get("control_uncovered") else "FAIL"
            if not result.get("control_uncovered"):
                any_fail = True
            print(f"\n{'='*60}")
            print(f"Control: {control[:80]}...")
            print(f"Sub-question: {sq_id}")
            print(f"Verdict: {verdict}")
            print(f"LLM calls this run: {result.get('llm_calls_used', 0)}")
            
            if result.get("tagged_control_findings"):
                print(f"  Tagged findings for control ({len(result['tagged_control_findings'])}):")
                for f in result["tagged_control_findings"]:
                    print(f"    source={f['source_id']} verified={f['verified']} sim={f['similarity']:.3f} claim='{f['claim'][:80]}...'")
            
            if result.get("original_coverage_changed"):
                print(f"  WARNING: Original details coverage CHANGED!")
                print(f"    Stored uncovered: {result.get('stored_uncovered')}")
                print(f"    New uncovered (orig): {result.get('new_uncovered_original')}")
    
    # Summary table
    print(f"\n{'='*80}")
    print(f"SUMMARY TABLE")
    print(f"{'='*80}")
    print(f"{'Sub-question':<20} {'Control':<50} {'Verdict':<6}")
    print(f"{'-'*80}")
    
    for r in all_results:
        verdict = "PASS" if r.get("control_uncovered") else "FAIL"
        control_short = r.get("control_detail", "N/A")[:48]
        print(f"{r.get('sub_question_id','N/A'):<20} {control_short:<50} {verdict:<6}")
    
    print(f"\nTotal LLM calls: {total_llm_calls}")
    
    if any_fail:
        print(f"\nRESULT: FAIL - at least one control was covered (over-tagging detected)")
        sys.exit(1)
    else:
        print(f"\nRESULT: PASS - all controls correctly uncovered")
        sys.exit(0)


if __name__ == "__main__":
    main()