#!/usr/bin/env python3
"""
Export judged (finding, aspect) pairs of ONE pipeline run as a blind labeling CSV (no judge columns) + a sidecar JSON with the ids and the stored verdict.

  python tests/export_run_rows.py --query-id <id> --focus "How is training,How is long-sequence" --n-other 25 --seed 5 [--exclude-claims file.txt]

focus   = prefixes of the sub-questions whose pairs are ALL exported (here the multi-entity comparison sub-questions)
n-other = a seeded random sample of pairs from the other sub-questions
exclude = a text file with one claim prefix per line: pairs whose claim starts with it are left out (rows whose verdict/reason the labeler has already seen)
Never overwrites: the output names carry a timestamp.
"""
import argparse
import csv
import json
import random
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv  # noqa: E402

load_dotenv()
from apps.api.services.db_service import supabase  # noqa: E402

FIELDS = ["row_id", "sub_question_id", "aspect_idx", "aspect_text", "source_id", "claim", "quote", "label", "notes"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query-id", required=True)
    ap.add_argument("--focus", default="")
    ap.add_argument("--n-other", type=int, default=25)
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--exclude-claims")
    ap.add_argument("--out-dir", default="reports")
    args = ap.parse_args()

    if len(args.query_id) < 36:      # allow the 8-character prefix used in the reports
        ids = [r["id"] for r in supabase.table("research_queries").select("id").execute().data if r["id"].startswith(args.query_id)]
        if len(ids) != 1:
            raise SystemExit(f"query id prefix {args.query_id!r} matches {len(ids)} queries")
        args.query_id = ids[0]
    exclude = [l.strip() for l in Path(args.exclude_claims).read_text(encoding="utf-8").splitlines() if l.strip()] if args.exclude_claims else []
    focus = [f.strip() for f in args.focus.split(",") if f.strip()]
    sqs = supabase.table("sub_questions").select("id,main_topic").eq("query_id", args.query_id).execute().data
    focus_pairs, other_pairs, excluded = [], [], 0
    for sq in sqs:
        is_focus = any(sq["main_topic"].startswith(f) for f in focus)
        for d in supabase.table("digests").select("source_id,source_title,findings").eq("sub_question_id", sq["id"]).execute().data:
            for f in d["findings"]:
                for a, v in (f.get("judge") or {}).items():
                    if not f.get("verified") or v.get("final") not in ("yes", "partial", "no"):
                        continue
                    if any(f["claim"].startswith(x) for x in exclude):
                        excluded += 1
                        continue
                    pair = {"sub_question_id": sq["id"], "aspect_idx": int(a), "aspect_text": v.get("aspect") or "", "source_id": d["source_id"],
                            "claim": f["claim"], "quote": f["quote"], "_stored": {k: v.get(k) for k in ("final", "quote_supports_claim", "answers_aspect", "reason")},
                            "_topic": sq["main_topic"][:60]}
                    (focus_pairs if is_focus else other_pairs).append(pair)
    rng = random.Random(args.seed)
    rng.shuffle(other_pairs)
    chosen = focus_pairs + other_pairs[:args.n_other]
    rng.shuffle(chosen)
    for i, p in enumerate(chosen, 1):
        p["row_id"] = str(i)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    out_csv, out_json = Path(args.out_dir) / f"tag_audit_run_{args.query_id[:8]}_{stamp}.csv", Path(args.out_dir) / f"tag_audit_run_{args.query_id[:8]}_verdicts_{stamp}.json"
    with open(out_csv, "x", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows([{**p, "label": "", "notes": ""} for p in chosen])
    with open(out_json, "x", encoding="utf-8") as f:
        json.dump({p["row_id"]: {k: v for k, v in p.items() if k.startswith("_") or k in ("sub_question_id", "aspect_idx", "source_id")} for p in chosen}, f, indent=1, ensure_ascii=False)
    assert not any(k in FIELDS for k in ("final", "_stored", "verdict")), "judge data must not be in the CSV"
    print(f"wrote {out_csv} ({len(chosen)} rows: {len(focus_pairs)} focus + {min(args.n_other, len(other_pairs))} other; {excluded} excluded pairs) and {out_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
