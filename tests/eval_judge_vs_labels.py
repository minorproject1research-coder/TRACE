#!/usr/bin/env python3
"""
tests/eval_judge_vs_labels.py

Calibration script to evaluate judge against labeled audit CSVs.

Usage:
    python tests/eval_judge_vs_labels.py --csv reports/tag_audit_labeled.csv reports/tag_audit_labeled_round2.csv reports/tag_audit_labeled_round3.csv

Labels: 1 = directly answers, 0.5 = partial, 0 = no
Maps: judge "yes" -> 1, "partial" -> 0.5, "no" -> 0

Reports:
- Confusion matrix
- Overall agreement
- Strict precision (judge "yes" vs label == 1)
- Lenient precision (judge "yes" vs label >= 0.5)
- Recall (label == 1)
- Disagreements sorted with false "yes" first

Gate: PASS if strict precision >= 0.85 AND lenient precision >= 0.95 AND recall >= 0.60

NOTE: These labels were produced by an LLM. Disagreement list should be spot-checked by a human.
"""
import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Setup
sys.path.insert(0, str(Path(__file__).parent.parent))

from apps.api.agents.stage3_summarizer.evidence_judge import (
    judge_candidates,
    _cache_key,
)

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Gate thresholds
STRICT_PRECISION_THRESHOLD = 0.85
LENIENT_PRECISION_THRESHOLD = 0.95
RECALL_THRESHOLD = 0.60


def load_labeled_csvs(csv_paths: List[str]) -> List[Dict]:
    """Load and merge labeled CSV files."""
    all_rows = []
    for path in csv_paths:
        p = Path(path)
        if not p.exists():
            logger.warning(f"File not found: {path}")
            continue
        with open(p, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["_source_file"] = p.name
                all_rows.append(row)
    logger.info(f"Loaded {len(all_rows)} rows from {len(csv_paths)} CSV files")
    return all_rows


def map_judge_verdict(verdict: Dict) -> float:
    """Map judge verdict to numeric label."""
    final = verdict.get("final", "error")
    if final == "yes":
        return 1.0
    elif final == "partial":
        return 0.5
    elif final == "no":
        return 0.0
    else:  # error
        return -1.0


def map_label(label_str: str) -> float:
    """Map string label to numeric."""
    try:
        return float(label_str)
    except (ValueError, TypeError):
        return -1.0


def run_judge_on_rows(rows: List[Dict]) -> List[Dict]:
    """Run judge on all rows and return results with predictions."""
    import hashlib
    # Build judge items with proper ID format: a{aspect_idx}_s{source_id}_f{finding_idx}
    # For eval, we use aspect_idx=0, source_id=row_{row_id}, finding_idx=0
    items = []
    for i, row in enumerate(rows):
        aspect = row.get("aspect_text") or row.get("detail_text", "")
        claim = row.get("claim", "")
        quote = row.get("quote", "")
        
        if not aspect or not claim or not quote:
            logger.warning(f"Row {i}: missing aspect/claim/quote, skipping")
            items.append(None)
            continue
        
        items.append({
            "id": f"a0_srow_{i}_f0",
            "aspect": aspect,
            "claim": claim,
            "quote": quote,
            "context": "",  # No chunk context available in CSV
        })
    
    # Filter valid items
    valid_items = [(i, item) for i, item in enumerate(items) if item is not None]
    if not valid_items:
        logger.warning("No valid items to judge")
        return rows
    
    item_list = [item for _, item in valid_items]
    
    # Run judge
    logger.info(f"Running judge on {len(item_list)} items...")
    verdicts = judge_candidates(item_list)
    
    # Map results back to rows
    results = []
    for orig_idx, item in valid_items:
        # The verdict key is (aspect_idx, source_id, claim_hash)
        # aspect_idx is 0 for all (single aspect per row), source_id from item id
        source_id = item["id"].split("_")[1][1:] if "_" in item["id"] else "src"
        claim_hash = hashlib.sha256(item["claim"].encode()).hexdigest()[:16]
        verdict_key = (0, source_id, claim_hash)
        v = verdicts.get(verdict_key, {})
        judge_verdict = v.get("verdict", {})
        pred = map_judge_verdict(judge_verdict)
        
        row = rows[orig_idx].copy()
        row["_judge_verdict"] = judge_verdict
        row["_pred"] = pred
        results.append(row)
    
    # Add rows that were skipped
    for i, item in enumerate(items):
        if item is None:
            row = rows[i].copy()
            row["_judge_verdict"] = {"final": "error", "reason": "missing data"}
            row["_pred"] = -1.0
            results.append(row)
    
    return results


def compute_confusion_matrix(y_true: List[float], y_pred: List[float], labels: List[float] = [0, 0.5, 1]) -> np.ndarray:
    """Compute confusion matrix."""
    n = len(labels)
    cm = np.zeros((n, n), dtype=int)
    label_to_idx = {l: i for i, l in enumerate(labels)}
    for t, p in zip(y_true, y_pred):
        if t in label_to_idx and p in label_to_idx:
            cm[label_to_idx[t], label_to_idx[p]] += 1
    return cm


def compute_metrics(y_true: List[float], y_pred: List[float]) -> Dict:
    """Compute precision, recall, agreement metrics."""
    # Filter valid labels
    valid_pairs = [(t, p) for t, p in zip(y_true, y_pred) if t >= 0 and p >= 0]
    if not valid_pairs:
        return {}
    
    y_t = [t for t, _ in valid_pairs]
    y_p = [p for _, p in valid_pairs]
    
    # Overall agreement
    agreement = sum(1 for t, p in valid_pairs if t == p) / len(valid_pairs)
    
    # Strict precision: judge "yes" (1) vs label == 1
    judge_yes = [p for t, p in valid_pairs if p == 1]
    true_pos_strict = sum(1 for t, p in valid_pairs if p == 1 and t == 1)
    strict_precision = true_pos_strict / len(judge_yes) if judge_yes else 0
    
    # Lenient precision: judge "yes" (1) vs label >= 0.5
    true_pos_lenient = sum(1 for t, p in valid_pairs if p == 1 and t >= 0.5)
    lenient_precision = true_pos_lenient / len(judge_yes) if judge_yes else 0
    
    # Recall: label == 1 captured by judge "yes"
    label_ones = [t for t, p in valid_pairs if t == 1]
    recall = true_pos_strict / len(label_ones) if label_ones else 0
    
    # Per-class precision/recall
    class_metrics = {}
    for label in [0, 0.5, 1]:
        pred_as_label = sum(1 for t, p in valid_pairs if p == label)
        true_as_label = sum(1 for t, p in valid_pairs if t == label)
        true_pos = sum(1 for t, p in valid_pairs if t == label and p == label)
        prec = true_pos / pred_as_label if pred_as_label else 0
        rec = true_pos / true_as_label if true_as_label else 0
        class_metrics[label] = {"precision": prec, "recall": rec, "support": true_as_label}
    
    return {
        "agreement": agreement,
        "strict_precision": strict_precision,
        "lenient_precision": lenient_precision,
        "recall": recall,
        "class_metrics": class_metrics,
        "n_valid": len(valid_pairs),
    }


def print_confusion_matrix(cm: np.ndarray, labels: List[float] = [0, 0.5, 1]):
    """Print confusion matrix nicely."""
    print("\n" + "="*60)
    print("CONFUSION MATRIX (rows=true, cols=predicted)")
    print("="*60)
    header = "       " + "  ".join(f"pred_{l}" for l in labels)
    print(header)
    for i, label in enumerate(labels):
        row = f"true_{label}: " + "  ".join(f"{cm[i,j]:4d}" for j in range(len(labels)))
        print(row)


def _sanitize(s: str) -> str:
    """Replace non-ASCII characters for safe console output."""
    return s.encode('ascii', 'replace').decode('ascii')

def print_disagreements(rows: List[Dict]):
    """Print disagreements sorted with false 'yes' first."""
    print("\n" + "="*80)
    print("DISAGREEMENTS (sorted: false 'yes' first)")
    print("="*80)
    
    disagreements = []
    for row in rows:
        label = map_label(row.get("label", ""))
        pred = row.get("_pred", -1)
        if label >= 0 and pred >= 0 and label != pred:
            disagreements.append(row)
    
    # Sort: false "yes" (pred=1, label!=1) first, then by label
    def sort_key(r):
        pred = r.get("_pred", -1)
        label = map_label(r.get("label", ""))
        if pred == 1 and label != 1:
            return (0, label)  # false yes first
        return (1, label)
    
    disagreements.sort(key=sort_key)
    
    for i, row in enumerate(disagreements):
        label = map_label(row.get("label", ""))
        pred = row.get("_pred", -1)
        verdict = row.get("_judge_verdict", {})
        reason = _sanitize(verdict.get("reason", "")[:150])
        notes = _sanitize(row.get("notes", "")[:150]) if row.get("notes") else ""
        
        pred_str = {1: "yes", 0.5: "partial", 0: "no"}.get(pred, "error")
        label_str = {1: "yes", 0.5: "partial", 0: "no"}.get(label, "?")
        
        print(f"\n[{i+1}] Row {row.get('row_id', '?')} | {row.get('_source_file', '')}")
        print(f"    Aspect: {_sanitize(row.get('aspect_text') or row.get('detail_text', '')[:100])}")
        print(f"    Claim:  {_sanitize(row.get('claim', '')[:100])}")
        print(f"    Quote:  {_sanitize(row.get('quote', '')[:80])}")
        print(f"    Label:  {label_str}  |  Judge: {pred_str}")
        print(f"    Reason: {reason}")
        if notes:
            print(f"    Notes:  {notes}")


def print_gate_result(metrics: Dict):
    """Print gate PASS/FAIL result."""
    strict = metrics.get("strict_precision", 0)
    lenient = metrics.get("lenient_precision", 0)
    recall = metrics.get("recall", 0)
    
    passed = (
        strict >= STRICT_PRECISION_THRESHOLD and
        lenient >= LENIENT_PRECISION_THRESHOLD and
        recall >= RECALL_THRESHOLD
    )
    
    print("\n" + "="*60)
    print("GATE RESULT")
    print("="*60)
    print(f"Strict precision (judge 'yes' vs label==1):  {strict:.3f} (need >= {STRICT_PRECISION_THRESHOLD})")
    print(f"Lenient precision (judge 'yes' vs label>=0.5): {lenient:.3f} (need >= {LENIENT_PRECISION_THRESHOLD})")
    print(f"Recall (label==1 captured by judge 'yes'):   {recall:.3f} (need >= {RECALL_THRESHOLD})")
    print()
    if passed:
        print("GATE: PASS")
    else:
        print("GATE: FAIL")
    
    return passed


def main():
    parser = argparse.ArgumentParser(description="Evaluate judge against labeled CSVs")
    parser.add_argument("--csv", nargs="+", required=True, help="Labeled CSV files")
    parser.add_argument("--mock", action="store_true", help="Mock judge responses (for testing)")
    args = parser.parse_args()
    
    # Load labeled data
    rows = load_labeled_csvs(args.csv)
    if not rows:
        logger.error("No rows loaded")
        sys.exit(1)
    
    # Check required columns
    required_cols = ["aspect_text", "claim", "quote", "label"]
    for col in required_cols:
        if col not in rows[0]:
            # Try alternative column names
            if col == "aspect_text" and "detail_text" in rows[0]:
                continue
            logger.error(f"Missing required column: {col}")
            sys.exit(1)
    
    mode_banner = "MOCK" if args.mock else "REAL"
    print("="*80)
    print(f"JUDGE CALIBRATION EVALUATION - MODE: {mode_banner}")
    print("="*80)
    print("NOTE: These labels were produced by an LLM.")
    print("      Disagreement list should be spot-checked by a human.")
    print("="*80)
    if args.mock:
        print("WARNING: Running in MOCK mode - results are NOT from real judge endpoint!")
        print("="*80)
    
    if args.mock:
        # Mock judge responses for testing
        logger.info("Mock mode: using labels as judge predictions")
        results = []
        for row in rows:
            label = map_label(row.get("label", ""))
            row_copy = row.copy()
            row_copy["_judge_verdict"] = {"final": {1: "yes", 0.5: "partial", 0: "no"}.get(label, "error")}
            row_copy["_pred"] = label
            results.append(row_copy)
    else:
        # Run real judge
        results = run_judge_on_rows(rows)
    
    # Extract labels and predictions
    y_true = []
    y_pred = []
    for row in results:
        label = map_label(row.get("label", ""))
        pred = row.get("_pred", -1)
        if label >= 0 and pred >= 0:
            y_true.append(label)
            y_pred.append(pred)
    
    if not y_true:
        logger.error("No valid label/prediction pairs")
        sys.exit(1)
    
    # Compute metrics
    metrics = compute_metrics(y_true, y_pred)
    cm = compute_confusion_matrix(y_true, y_pred)
    
    # Print results
    print_confusion_matrix(cm)
    
    print("\n" + "="*60)
    print("OVERALL METRICS")
    print("="*60)
    print(f"Agreement:           {metrics.get('agreement', 0):.3f}")
    print(f"Strict precision:    {metrics.get('strict_precision', 0):.3f}")
    print(f"Lenient precision:   {metrics.get('lenient_precision', 0):.3f}")
    print(f"Recall (label==1):   {metrics.get('recall', 0):.3f}")
    print(f"Valid pairs:         {metrics.get('n_valid', 0)}")
    
    print("\nPer-class metrics:")
    for label, m in metrics.get("class_metrics", {}).items():
        print(f"  Label {label}: precision={m['precision']:.3f}, recall={m['recall']:.3f}, support={m['support']}")
    
    # Print disagreements
    print_disagreements(results)
    
    # Gate result
    passed = print_gate_result(metrics)
    
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    import hashlib
    main()