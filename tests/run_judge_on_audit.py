#!/usr/bin/env python3
"""
Run judge on audit_tag_precision export and write verdicts to JSON file.
Usage: python tests/run_judge_on_audit.py --in reports/tag_audit_sample_seed11.csv --out reports/judge_verdicts_seed11.json
"""
import argparse
import csv
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from apps.api.agents.stage3_summarizer.evidence_judge import judge_candidates

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run judge on audit CSV and write verdicts to JSON")
    parser.add_argument("--in", dest="in_file", required=True, help="Input CSV file from audit_tag_precision.py export")
    parser.add_argument("--out", dest="out_file", required=True, help="Output JSON file for judge verdicts")
    args = parser.parse_args()
    
    # Load CSV
    rows = []
    with open(args.in_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    
    logger.info(f"Loaded {len(rows)} rows from {args.in_file}")
    
    # Build judge items
    items = []
    for row in rows:
        aspect = row.get("aspect_text") or row.get("detail_text", "")
        claim = row.get("claim", "")
        quote = row.get("quote", "")
        
        if not aspect or not claim or not quote:
            logger.warning(f"Row {row.get('row_id', '?')}: missing aspect/claim/quote, skipping")
            continue
        
        items.append({
            "id": f"a0_srow_{row['row_id']}_f0",
            "aspect": aspect,
            "claim": claim,
            "quote": quote,
            "context": "",  # No chunk context available in CSV
        })
    
    logger.info(f"Running judge on {len(items)} items...")
    
    # Run judge (requires JUDGE_URL env var)
    verdicts = judge_candidates(items)
    
    # Write results to JSON
    output = {}
    for row in rows:
        row_id = row.get("row_id", "?")
        if not row_id or row_id == "?":
            continue
        
        # Find matching verdict - item ID format is "a0_srow_{row_id}_f0"
        source_id = f"row_{row_id}"
        claim = row.get("claim", "")
        claim_hash = hashlib.sha256(claim.encode()).hexdigest()[:16]
        verdict_key = (0, source_id, claim_hash)
        
        v = verdicts.get(verdict_key, {})
        verdict = v.get("verdict", {})
        
        output[row_id] = {
            "final": verdict.get("final"),
            "quote_supports_claim": verdict.get("quote_supports_claim"),
            "answers_aspect": verdict.get("answers_aspect"),
            "reason": verdict.get("reason"),
            "raw_output": v.get("raw_output", ""),
            "error": v.get("error"),
        }
    
    Path(args.out_file).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Wrote {len(output)} verdicts to {args.out_file}")


if __name__ == "__main__":
    import hashlib
    main()