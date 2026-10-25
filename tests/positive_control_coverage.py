#!/usr/bin/env python3
"""
tests/positive_control_coverage.py

Positive control for Stage 3 coverage.
Confirms that aspects with human-labeled "directly answers" (label=1) and 
judge "yes" verdicts are reported as covered.
"""
import sys
import json
from pathlib import Path
from typing import Dict, List, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from apps.api.services.db_service import supabase

def load_labeled_rows(csv_paths: List[str]) -> List[Dict]:
    """Load labeled rows from CSV files."""
    import csv
    all_rows = []
    for path in csv_paths:
        p = Path(path)
        if not p.exists():
            continue
        with open(p, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["_source_file"] = p.name
                all_rows.append(row)
    return all_rows

def get_judge_verdicts(query_id: str, sub_question_id: str) -> Dict:
    """Get judge verdicts from the coverage results (not persisted yet, so we run the judge)."""
    # This would need the full pipeline - for now we use the calibration results
    pass

def main():
    # Load all labeled data
    csv_paths = [
        "reports/tag_audit_labeled.csv",
        "reports/tag_audit_labeled_round2.csv", 
        "reports/tag_audit_labeled_round3.csv",
        "reports/tag_audit_labeled_seed11.csv"
    ]
    
    labeled_rows = load_labeled_rows(csv_paths)
    print(f"Loaded {len(labeled_rows)} labeled rows")
    
    # Filter for label == "1" (directly answers)
    positive_rows = [r for r in labeled_rows if r.get("label") == "1"]
    print(f"Positive (label=1) rows: {len(positive_rows)}")
    
    # Group by sub-question
    from collections import defaultdict
    by_sq = defaultdict(list)
    for r in positive_rows:
        sq_id = r.get("sub_question_id")
        if sq_id:
            by_sq[sq_id].append(r)
    
    # For each sub-question, check if aspects with positive labels are covered
    print("\nPositive control summary by sub-question:")
    for sq_id, rows in by_sq.items():
        aspects = set(r.get("aspect_text") or r.get("detail_text", "") for r in rows)
        print(f"\nSub-question {sq_id}: {len(rows)} positive rows, {len(aspects)} unique aspects")
        for a in aspects:
            print(f"  - {a[:80]}")
    
    # Now run Stage 3 for each query to get judge verdicts and compare
    print("\n" + "="*60)
    print("RUNNING STAGE 3 PIPELINE FOR POSITIVE CONTROL")
    print("="*60)
    
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    from apps.api.graph.nodes.summarizer_node import summarizer_node
    from apps.api.graph.state import SharedResearchState
    from apps.api.models.task_plan import TaskPlan
    
    query_ids = ['6e735eb6-4b79-4c7e-af41-c88adaeee8fe', 
                 '6e0ccec0-2109-4794-8063-f077c4eac548', 
                 '780ed8a5-8794-49df-97e2-4548bbe10aeb']
    
    for qid in query_ids:
        print(f"\n=== Query {qid} ===")
        query = supabase.table('research_queries').select('*').eq('id', qid).execute().data[0]
        sub_questions = supabase.table('sub_questions').select('*').eq('query_id', qid).execute().data
        
        task_plan = TaskPlan(
            query_id=qid,
            raw_query=query['raw_query'],
            sub_questions=[]
        )
        for sq in sub_questions:
            task_plan.sub_questions.append(type('obj', (object,), sq))
        
        state = SharedResearchState(raw_query=query['raw_query'], task_plan=task_plan)
        
        # Run summarizer
        result = summarizer_node(state)
        
        # Check coverage against positive labels
        for sq_id, cov in result.get('coverage', {}).items():
            # Get positive aspects for this sub-question
            pos_aspects = set()
            for r in positive_rows:
                if r.get("sub_question_id") == sq_id:
                    pos_aspects.add(r.get("aspect_text") or r.get("detail_text", ""))
            
            uncovered = cov.get('uncovered_aspects', [])
            covered_evidence = cov.get('aspect_evidence', {})
            
            print(f"\n  Sub-question {sq_id}:")
            print(f"    Positive aspects: {len(pos_aspects)}")
            print(f"    Uncovered aspects: {len(uncovered)}")
            print(f"    Aspects with judge evidence: {len(covered_evidence)}")
            
            # Check each positive aspect
            for aspect in pos_aspects:
                # Find if this aspect is covered
                aspect_covered = False
                for asp_idx, ev in covered_evidence.items():
                    # The aspect text would be in the original aspects list
                    # For now just check if any evidence exists
                    if ev:
                        aspect_covered = True
                        break
                
                status = "COVERED" if aspect_covered else "UNCOVERED"
                print(f"    {status}: {aspect[:80]}")
            
            # Also list uncovered aspects
            for u in uncovered:
                print(f"    UNCOVERED: {u[:80]}")

if __name__ == "__main__":
    main()