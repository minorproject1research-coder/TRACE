#!/usr/bin/env python3
"""
Script 1: Audit tag precision for Stage 3 answers_details tags.

MODE export (default):
  python tests/audit_tag_precision.py export --query-ids <id1,id2,...> --n 40 --out reports/tag_audit_sample.csv

MODE score:
  python tests/audit_tag_precision.py score --in reports/tag_audit_sample.csv
"""

import argparse
import csv
import json
import logging
import math
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --- Constants ---
DEFAULT_N_TAGGED = 40
DEFAULT_N_UNTAGGED = 10
DEFAULT_SEED = 7
TARGET_PRECISION_STRICT = 0.85
TARGET_PRECISION_LENIENT = 0.92
MIN_AUC_FOR_RAISE_THRESHOLD = 0.75

# Setup
sys.path.insert(0, str(Path(__file__).parent.parent))

from apps.api.services.db_service import (
    get_papers_for_stage3,
    get_web_sources_for_stage3,
    supabase,
)
from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder
from apps.api.agents.stage3_summarizer.chunk_selector import _clean_topic
from apps.api.agents.stage3_summarizer.coverage_check import MIN_TAG_SIM
from apps.api.agents.stage3_summarizer.detail_aspects import (
    flatten_aspects,
    split_detail_aspects,
)

logging.basicConfig(level=logging.WARNING, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_latest_query_ids(n: int = 3) -> List[str]:
    """Get the N most recent query IDs from digests table."""
    result = supabase.table("digests").select("query_id, created_at").order("created_at", desc=True).execute()
    if not result.data:
        return []
    seen = set()
    qids = []
    for row in result.data:
        qid = row["query_id"]
        if qid not in seen:
            seen.add(qid)
            qids.append(qid)
            if len(qids) >= n:
                break
    return qids


def load_digests_for_queries(query_ids: List[str]) -> List[Dict]:
    if not query_ids:
        return []
    result = supabase.table("digests").select("*").in_("query_id", query_ids).execute()
    return result.data or []


def load_sub_questions(query_ids: List[str]) -> List[Dict]:
    if not query_ids:
        return []
    result = supabase.table("sub_questions").select("*").in_("query_id", query_ids).execute()
    return result.data or []


def load_coverage_results(query_ids: List[str]) -> List[Dict]:
    if not query_ids:
        return []
    result = supabase.table("coverage_results").select("*").in_("query_id", query_ids).execute()
    return result.data or []


def compute_similarity(claim: str, aspect: str) -> float:
    if not claim or not aspect:
        return 0.0
    model = get_embedder()
    c_emb = model.encode([claim], normalize_embeddings=True)[0]
    d_emb = model.encode([aspect], normalize_embeddings=True)[0]
    return float(c_emb @ d_emb)


def extract_strength(tag: Any) -> str:
    """Extract strength from a tag (new format: dict, legacy: int)."""
    if isinstance(tag, dict):
        return tag.get("strength", "partial")
    return "partial"  # legacy int format


def export_mode(args):
    """Export tagged findings sample for human labeling."""
    query_ids = [q.strip() for q in args.query_ids.split(",")] if args.query_ids else get_latest_query_ids(3)
    logger.info(f"Loading digests for query_ids: {query_ids}")
    
    digests = load_digests_for_queries(query_ids)
    sub_questions = load_sub_questions(query_ids)
    coverage_results = load_coverage_results(query_ids)
    
    if not digests:
        logger.warning("No digests found for the given query IDs")
        return
    
    # Build lookups
    sq_map = {sq["id"]: sq for sq in sub_questions}
    cov_map = {(c["query_id"], c["sub_question_id"]): c for c in coverage_results}
    
    tagged_rows = []
    untagged_candidates = []
    covering_rows = []  # findings that actually cover a detail
    
    total_findings = 0
    total_tagged = 0
    tag_counts = {}
    multi_detail = 0
    strength_counts = {"full": 0, "partial": 0}
    aspect_coverage = {}  # aspect_text -> count of verified full-strength tags
    
    for d in digests:
        query_id = d.get("query_id")
        sub_q_id = d.get("sub_question_id")
        source_id = d.get("source_id")
        evidence_level = d.get("evidence_level", "full_text")
        
        sq = sq_map.get(sub_q_id)
        if not sq:
            logger.warning(f"Sub-question {sub_q_id} not found")
            continue
        
        main_topic = _clean_topic(sq.get("main_topic", ""))
        original_details = sq.get("detail_questions", [])
        aspects, aspect_to_detail = flatten_aspects(original_details, sub_q_id, main_topic)
        
        # Check coverage for this sub-question
        cov_key = (query_id, sub_q_id)
        coverage = cov_map.get(cov_key, {})
        uncovered_aspects = set(coverage.get("uncovered_aspects", []))
        
        for f in d.get("findings", []):
            total_findings += 1
            claim = f.get("claim", "")
            quote = f.get("quote", "")
            verified = f.get("verified", False)
            tags = f.get("answers_details", [])
            
            if tags:
                total_tagged += 1
                n_tags = len(tags)
                tag_counts[n_tags] = tag_counts.get(n_tags, 0) + 1
                if n_tags > 1:
                    multi_detail += 1
                
                for tag in tags:
                    detail_num = tag.get("detail") if isinstance(tag, dict) else tag
                    strength = extract_strength(tag)
                    strength_counts[strength] = strength_counts.get(strength, 0) + 1
                    
                    if 1 <= detail_num <= len(aspects):
                        aspect_text = aspects[detail_num - 1]
                        sim = compute_similarity(claim, aspect_text)
                        
                        # Check if this finding covers the aspect (verified + full strength + passes MIN_TAG_SIM)
                        is_covering = (
                            verified and 
                            strength == "full" and 
                            sim >= MIN_TAG_SIM and
                            aspect_text not in uncovered_aspects
                        )
                        
                        kind = "covering" if is_covering else "tagged"
                        
                        row = {
                            "row_id": "",
                            "kind": kind,
                            "query_id": query_id,
                            "sub_question_id": sub_q_id,
                            "main_topic": main_topic,
                            "aspect_text": aspect_text,
                            "strength": strength,
                            "claim": claim,
                            "quote": quote,
                            "similarity": f"{sim:.4f}",
                            "label": "",
                            "notes": "",
                        }
                        
                        if kind == "covering":
                            covering_rows.append(row)
                        else:
                            tagged_rows.append(row)
                        
                        # Track coverage per aspect (verified full-strength only)
                        if verified and strength == "full":
                            aspect_coverage[aspect_text] = aspect_coverage.get(aspect_text, 0) + 1
            else:
                # Untagged candidate
                if aspects and claim:
                    sims = [compute_similarity(claim, a) for a in aspects]
                    max_sim = max(sims)
                    best_idx = sims.index(max_sim)
                    untagged_candidates.append({
                        "max_sim": max_sim,
                        "best_aspect": aspects[best_idx],
                        "query_id": query_id,
                        "sub_question_id": sub_q_id,
                        "main_topic": main_topic,
                        "claim": claim,
                        "quote": f.get("quote", ""),
                        "verified": verified,
                        "evidence_level": evidence_level,
                    })
    
    # Print overall tag statistics
    print(f"\n{'='*60}")
    print(f"OVERALL TAG STATISTICS")
    print(f"{'='*60}")
    print(f"Total findings: {total_findings}")
    print(f"Tagged findings: {total_tagged}")
    print(f"Tagged fraction: {total_tagged/total_findings*100:.1f}%" if total_findings else "0%")
    print(f"Mean tags per tagged finding: {sum(k*v for k,v in tag_counts.items())/total_tagged:.2f}" if total_tagged else "0")
    print(f"Fraction with >1 detail: {multi_detail/total_tagged*100:.1f}%" if total_tagged else "0%")
    print(f"Strength distribution: {strength_counts}")
    print(f"Tag count distribution: {dict(sorted(tag_counts.items()))}")
    print(f"\nPer-aspect coverage (verified full-strength tags):")
    for aspect_text, count in sorted(aspect_coverage.items()):
        marker = " <-- THIN" if count == 1 else ""
        print(f"  [{count}] {aspect_text[:80]}...{marker}")
    
    # Stratified sample from tagged + covering rows
    random.seed(args.seed)
    
    all_tagged = tagged_rows + covering_rows
    
    # Group by (query_id, sub_question_id, aspect_text, strength)
    from collections import defaultdict
    groups = defaultdict(list)
    for row in all_tagged:
        key = (row["query_id"], row["sub_question_id"], row["aspect_text"], row["strength"])
        groups[key].append(row)
    
    # Stratified sampling
    all_keys = list(groups.keys())
    random.shuffle(all_keys)
    
    sampled = []
    n_per_group = max(1, args.n // len(all_keys)) if all_keys else 0
    
    for key in all_keys:
        group_rows = groups[key]
        random.shuffle(group_rows)
        take = min(n_per_group, len(group_rows))
        sampled.extend(group_rows[:take])
        if len(sampled) >= args.n:
            break
    
    if len(sampled) < args.n:
        remaining = [r for g in groups.values() for r in g if r not in sampled]
        random.shuffle(remaining)
        sampled.extend(remaining[:args.n - len(sampled)])
    
    sampled = sampled[:args.n]
    
    # Add untagged candidates (highest similarity)
    untagged_candidates.sort(key=lambda x: x["max_sim"], reverse=True)
    for uc in untagged_candidates[:args.n_untagged]:
        sampled.append({
            "row_id": "",
            "kind": "untagged",
            "query_id": uc["query_id"],
            "sub_question_id": uc["sub_question_id"],
            "main_topic": uc["main_topic"],
            "aspect_text": uc["best_aspect"],
            "strength": "",
            "claim": uc["claim"],
            "quote": uc["quote"],
            "similarity": f"{uc['max_sim']:.4f}",
            "label": "",
            "notes": "",
        })
    
    # Shuffle final order
    random.shuffle(sampled)
    
    # Assign row_ids and write CSV
    for i, row in enumerate(sampled):
        row["row_id"] = str(i + 1)
    
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    fieldnames = ["row_id", "kind", "query_id", "sub_question_id", "main_topic", 
                  "aspect_text", "strength", "claim", "quote", "similarity", "label", "notes"]
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sampled)
    
    print(f"\nExported {len(sampled)} rows to {output_path}")
    print(f"  Tagged: {sum(1 for r in sampled if r['kind'] == 'tagged')}")
    print(f"  Covering: {sum(1 for r in sampled if r['kind'] == 'covering')}")
    print(f"  Untagged: {sum(1 for r in sampled if r['kind'] == 'untagged')}")
    print(f"\nNext step: Fill in 'label' column (1=directly answers, 0.5=partially, 0=does not answer)")
    print(f"Then run: python tests/audit_tag_precision.py score --in {args.out}")


def compute_auc(label1_sims: List[float], label0_sims: List[float]) -> float:
    """Compute AUC-ROC for similarity as a classifier of label 1 vs 0."""
    if not label1_sims or not label0_sims:
        return 0.0
    # Mann-Whitney U statistic
    all_pairs = 0
    correct_pairs = 0
    for s1 in label1_sims:
        for s0 in label0_sims:
            all_pairs += 1
            if s1 > s0:
                correct_pairs += 1
            elif s1 == s0:
                correct_pairs += 0.5
    return correct_pairs / all_pairs if all_pairs > 0 else 0.5


def score_mode(args):
    input_path = Path(args.in_file)
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return
    
    rows = []
    with open(input_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    
    if not rows:
        print("No rows in input file")
        return
    
    tagged = [r for r in rows if r["kind"] in ("tagged", "covering")]
    untagged = [r for r in rows if r["kind"] == "untagged"]
    
    # Parse labels
    skipped = 0
    labeled_tagged = []
    for r in tagged:
        try:
            r["label_val"] = float(r["label"]) if r["label"] else None
        except ValueError:
            r["label_val"] = None
        if r["label_val"] is None:
            skipped += 1
        else:
            labeled_tagged.append(r)
    
    print(f"\n{'='*60}")
    print(f"TAG PRECISION SCORE")
    print(f"{'='*60}")
    print(f"Total tagged rows: {len(tagged)}")
    print(f"Labeled: {len(labeled_tagged)}")
    print(f"Skipped (empty label): {skipped}")
    
    if not labeled_tagged:
        print("No labeled rows to score")
        return
    
    # Overall precision
    strict_correct = sum(1 for r in labeled_tagged if r["label_val"] == 1.0)
    strict_precision = strict_correct / len(labeled_tagged)
    lenient_correct = sum(1 for r in labeled_tagged if r["label_val"] >= 0.5)
    lenient_precision = lenient_correct / len(labeled_tagged)
    
    label_counts = {}
    for r in labeled_tagged:
        label_counts[r["label_val"]] = label_counts.get(r["label_val"], 0) + 1
    
    print(f"\nStrict precision (label==1): {strict_precision:.3f} ({strict_correct}/{len(labeled_tagged)})")
    print(f"Lenient precision (label>=0.5): {lenient_precision:.3f} ({lenient_correct}/{len(labeled_tagged)})")
    print(f"Label distribution: {dict(sorted(label_counts.items()))}")
    
    # By strength
    for strength in ["full", "partial"]:
        strength_rows = [r for r in labeled_tagged if r.get("strength") == strength]
        if not strength_rows:
            continue
        s_strict = sum(1 for r in strength_rows if r["label_val"] == 1.0) / len(strength_rows)
        s_lenient = sum(1 for r in strength_rows if r["label_val"] >= 0.5) / len(strength_rows)
        print(f"\nStrength '{strength}' (n={len(strength_rows)}): strict={s_strict:.3f}, lenient={s_lenient:.3f}")
    
    # By compound vs non-compound (using aspect splitting)
    compound_rows = []
    non_compound_rows = []
    for r in labeled_tagged:
        aspect = r["aspect_text"]
        # Check if the parent detail was compound
        is_compound = False
        # We'd need original detail mapping - approximate by checking if aspect contains " and " or " or "
        # But better: we can't easily determine from exported data. Skip compound breakdown for now.
        non_compound_rows.append(r)
    
    # False tags
    false_tags = [r for r in labeled_tagged if r["label_val"] == 0.0]
    if false_tags:
        print(f"\n{'='*60}")
        print(f"FALSE TAGS (label=0) - {len(false_tags)} rows:")
        for r in false_tags[:10]:
            print(f"  Claim: {r['claim'][:80]}...")
            print(f"  Aspect: {r['aspect_text'][:80]}...")
            print(f"  Strength: {r.get('strength', 'N/A')}")
            print(f"  Similarity: {r['similarity']}")
            print()
    
    # Similarity distributions
    label1_sims = [float(r["similarity"]) for r in labeled_tagged if r["label_val"] == 1.0]
    label0_sims = [float(r["similarity"]) for r in labeled_tagged if r["label_val"] == 0.0]
    label05_sims = [float(r["similarity"]) for r in labeled_tagged if r["label_val"] == 0.5]
    
    def stats_str(vals):
        if not vals:
            return "N/A"
        sorted_vals = sorted(vals)
        return f"min={min(vals):.3f}, median={sorted_vals[len(vals)//2]:.3f}, max={max(vals):.3f}, n={len(vals)}"
    
    print(f"\nSimilarity distributions:")
    print(f"  Label 1:   {stats_str(label1_sims)}")
    print(f"  Label 0.5: {stats_str(label05_sims)}")
    print(f"  Label 0:   {stats_str(label0_sims)}")
    
    # AUC
    auc = compute_auc(label1_sims, label0_sims)
    print(f"\nAUC (similarity vs label 1 vs 0): {auc:.3f}")
    
    # Verdict
    print(f"\n{'='*60}")
    print(f"VERDICT")
    print(f"{'='*60}")
    passed = strict_precision >= TARGET_PRECISION_STRICT and lenient_precision >= TARGET_PRECISION_LENIENT
    if passed:
        print(f"PASS: strict={strict_precision:.3f} >= {TARGET_PRECISION_STRICT}, lenient={lenient_precision:.3f} >= {TARGET_PRECISION_LENIENT}")
    else:
        print(f"FAIL: strict={strict_precision:.3f} (need >= {TARGET_PRECISION_STRICT}), lenient={lenient_precision:.3f} (need >= {TARGET_PRECISION_LENIENT})")
        print(f"\nRecommended actions:")
        actions = []
        if strict_precision < TARGET_PRECISION_STRICT:
            actions.append("1. Tighten the tagging instruction in digest_generator.py")
        if len(label0_sims) > 0 and len(label1_sims) > 0:
            if min(label1_sims) < max(label0_sims):
                actions.append("2. Consider if tagging criteria need clarification (overlap in similarity distributions)")
            else:
                if auc >= MIN_AUC_FOR_RAISE_THRESHOLD:
                    actions.append("3. Raise MIN_TAG_SIM (similarity distributions separate, AUC >= 0.75)")
        print(f"  AUC = {auc:.3f} (threshold for raising MIN_TAG_SIM: {MIN_AUC_FOR_RAISE_THRESHOLD})")
        for a in actions[:3]:
            print(f"  {a}")
    
    sys.exit(0 if passed else 1)


def main():
    parser = argparse.ArgumentParser(description="Audit tag precision for Stage 3 answers_details")
    subparsers = parser.add_subparsers(dest="mode", required=True)
    
    p_export = subparsers.add_parser("export", help="Export tagged findings sample for labeling")
    p_export.add_argument("--query-ids", help="Comma-separated query IDs (default: 3 most recent)")
    p_export.add_argument("--n", type=int, default=DEFAULT_N_TAGGED, help=f"Number of tagged findings to sample (default: {DEFAULT_N_TAGGED})")
    p_export.add_argument("--n-untagged", type=int, default=DEFAULT_N_UNTAGGED, help=f"Number of untagged high-similarity findings (default: {DEFAULT_N_UNTAGGED})")
    p_export.add_argument("--seed", type=int, default=DEFAULT_SEED, help=f"Random seed (default: {DEFAULT_SEED})")
    p_export.add_argument("--out", default="reports/tag_audit_sample.csv", help="Output CSV path")
    
    p_score = subparsers.add_parser("score", help="Score a labeled CSV")
    p_score.add_argument("--in", dest="in_file", required=True, help="Input CSV file with labels filled")
    
    args = parser.parse_args()
    
    if args.mode == "export":
        export_mode(args)
    elif args.mode == "score":
        score_mode(args)


if __name__ == "__main__":
    main()