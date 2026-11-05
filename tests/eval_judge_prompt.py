#!/usr/bin/env python3
"""
Evaluate the CURRENT judge (whatever prompt the model server runs; JUDGE_MODEL_ID names it) against labeled rows, and optionally compare with
the saved results of another run.

REAL run: calls the real judge endpoint (TRACE_LLM_URL). Never mocks. The judge sees NO surrounding passage here (the CSVs do not hold it).
Row ids are file-prefixed ("<file>:<row_id>"); every confusion matrix is asserted to sum to the number of rows.

  python tests/eval_judge_prompt.py --csv reports/tag_audit_labeled_targeted.csv reports/tag_audit_labeled.csv ... [--compare reports/judge_eval_X.json]

Writes reports/judge_eval_<JUDGE_MODEL_ID>_<yyyymmdd_hhmm>.json (one record per row) so a later run can be compared row by row.
Labels: 1 = directly answers, 0.5 = partial, 0 = no (assigned by an LLM). Judge: yes -> 1, partial -> 0.5, no -> 0.
Gate (handoff): strict yes-precision >= 0.85, lenient >= 0.95, recall of label 1 >= 0.60.
"""
import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv  # noqa: E402

load_dotenv()
from apps.api.agents.stage3_summarizer import evidence_judge  # noqa: E402

GATE = {"strict": 0.85, "lenient": 0.95, "recall": 0.60}
PRED = {"yes": 1.0, "partial": 0.5, "no": 0.0}


def load_rows(paths):
    rows, seen = [], set()
    for path in paths:
        p = Path(path)
        with open(p, "r", encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                aspect = r.get("aspect_text") or r.get("detail_text") or ""
                if not (aspect and r.get("claim") and r.get("quote")) or r.get("label", "").strip() == "":
                    continue
                key = f"{p.stem}:{r['row_id']}"
                assert key not in seen, f"duplicate row key {key}"
                seen.add(key)
                rows.append({"key": key, "file": p.stem, "aspect": aspect, "claim": r["claim"], "quote": r["quote"], "label": float(r["label"])})
    return rows


def judge_rows(rows):
    items = []
    for r in rows:
        items.append({"id": hashlib.sha256(f"{r['key']}|{r['aspect']}".encode()).hexdigest()[:16], "aspect_idx": 0, "source_id": r["key"],
                      "aspect": r["aspect"], "claim": r["claim"], "quote": r["quote"], "context": ""})
    verdicts = evidence_judge.judge_candidates(items)
    out = []
    for r in rows:
        v = verdicts.get((0, r["key"], hashlib.sha256(r["claim"].encode()).hexdigest()[:16]), {}).get("verdict") or {}
        out.append({**r, "final": v.get("final", "error"), "quote_supports_claim": v.get("quote_supports_claim"),
                    "answers_aspect": v.get("answers_aspect"), "reason": v.get("reason", "")})
    return out


def metrics(rows):
    ok = [r for r in rows if r["final"] in PRED]
    n = len(ok)
    cm = {t: Counter() for t in (0.0, 0.5, 1.0)}
    for r in ok:
        cm[r["label"]][PRED[r["final"]]] += 1
    assert sum(sum(c.values()) for c in cm.values()) == n, "confusion matrix does not sum to the number of judged rows"
    yes = [r for r in ok if r["final"] == "yes"]
    ones = [r for r in ok if r["label"] == 1.0]
    tp_strict = sum(1 for r in yes if r["label"] == 1.0)
    tp_len = sum(1 for r in yes if r["label"] >= 0.5)
    return {"n": len(rows), "judged": n, "errors": len(rows) - n, "judge_yes": len(yes), "label1": len(ones),
            "strict": tp_strict / len(yes) if yes else None, "lenient": tp_len / len(yes) if yes else None,
            "recall": tp_strict / len(ones) if ones else None,
            "agreement": sum(1 for r in ok if PRED[r["final"]] == r["label"]) / n if n else None,
            "confusion": {str(t): {str(p): c[p] for p in (0.0, 0.5, 1.0)} for t, c in cm.items()},
            "false_yes": [r["key"] for r in yes if r["label"] < 1.0], "false_yes_label0": [r["key"] for r in yes if r["label"] == 0.0],
            "missed_label1": [r["key"] for r in ones if r["final"] != "yes"]}


def fmt(x):
    return "  -  " if x is None else f"{x:.3f}"


def show(name, m):
    print(f"{name:<34} n={m['n']:<3} judge_yes={m['judge_yes']:<3} strict={fmt(m['strict'])} lenient={fmt(m['lenient'])} recall={fmt(m['recall'])} "
          f"agree={fmt(m['agreement'])} errors={m['errors']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", nargs="+", required=True)
    ap.add_argument("--compare", help="saved judge_eval_*.json of another prompt version")
    ap.add_argument("--split", help="json with {\"dev\": [row keys], \"test\": [row keys]}: also print metrics for each part, with the policy labels and with multi-system aspects capped at 0.5")
    ap.add_argument("--out-dir", default="reports")
    args = ap.parse_args()

    cfg = evidence_judge._get_config()
    if not cfg["JUDGE_URL"]:
        print("ERROR: no judge URL (TRACE_LLM_URL). Nothing was evaluated.")
        return 2
    host = cfg["JUDGE_URL"].split("//")[-1].split("/")[0]
    print(f"REAL judge run | endpoint {host} | JUDGE_MODEL_ID={cfg['JUDGE_MODEL_ID']} | no surrounding passage")
    rows = load_rows(args.csv)
    print(f"{len(rows)} labeled rows from {len(args.csv)} file(s)")
    results = judge_rows(rows)
    errors = sum(1 for r in results if r["final"] not in PRED)
    if errors:
        print(f"WARNING: {errors} row(s) came back as errors and are excluded from the metrics")
    if errors == len(results):
        reasons = Counter(r["reason"][:100] for r in results)
        print(f"INCONCLUSIVE: every row failed ({dict(reasons)}). Nothing saved, no gate verdict.")
        return 2

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    out = Path(args.out_dir) / f"judge_eval_{cfg['JUDGE_MODEL_ID']}_{stamp}.json"
    out.write_text(json.dumps({"judge_model_id": cfg["JUDGE_MODEL_ID"], "rows": results}, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\nPER FILE")
    by_file = defaultdict(list)
    for r in results:
        by_file[r["file"]].append(r)
    for f, rs in by_file.items():
        show(f, metrics(rs))
    # pooled: the same (aspect, claim, quote) can appear in several files; count it once
    seen, pooled = set(), []
    for r in results:
        k = (r["aspect"], r["claim"], r["quote"])
        if k not in seen:
            seen.add(k)
            pooled.append(r)
    print(f"\nPOOLED (deduplicated: {len(pooled)} of {len(results)} rows)")
    pm = metrics(pooled)
    show("pooled", pm)
    print("confusion (rows = label, columns = judge 0 / 0.5 / 1):")
    for t, c in pm["confusion"].items():
        print(f"  label {t:<4} {c['0.0']:>3} {c['0.5']:>3} {c['1.0']:>3}")
    gate = (pm["strict"] or 0) >= GATE["strict"] and (pm["lenient"] or 0) >= GATE["lenient"] and (pm["recall"] or 0) >= GATE["recall"]
    print(f"GATE (strict >= {GATE['strict']}, lenient >= {GATE['lenient']}, recall >= {GATE['recall']}): {'PASS' if gate else 'FAIL'}   (pooled; LLM labels)")
    print("false yes with label 0:", pm["false_yes_label0"])
    print("label-1 rows the judge did not call yes:", pm["missed_label1"])

    if args.split:
        sp = json.loads(Path(args.split).read_text(encoding="utf-8"))
        by_key = {r["key"]: r for r in results}
        print("\nSPLIT (policy labels | strict labels: aspects listing several systems capped at 0.5)")
        for part in ("dev", "test"):
            rs = [by_key[k] for k in sp[part] if k in by_key]
            capped = [dict(r, label=min(r["label"], 0.5)) if "transformers, and Mamba" in r["aspect"] else r for r in rs]
            show(f"{part} (policy)", metrics(rs))
            show(f"{part} (strict)", metrics(capped))
    if args.compare:
        old = {r["key"]: r for r in json.loads(Path(args.compare).read_text(encoding="utf-8"))["rows"]}
        print(f"\nCOMPARISON with {Path(args.compare).name} ({json.loads(Path(args.compare).read_text(encoding='utf-8')).get('judge_model_id')})")
        changed = [(old[r["key"]]["final"], r["final"], r) for r in results if r["key"] in old and old[r["key"]]["final"] != r["final"]]
        print(f"rows in both: {sum(1 for r in results if r['key'] in old)}; verdict changed on {len(changed)}")
        for o, n, r in sorted(changed, key=lambda x: (x[0], x[1])):
            print(f"  {r['key']:<40} label {r['label']:<4} {o:>7} -> {n:<7}  {r['claim'][:60]}")
    print(f"\nsaved {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
