"""Run Stage 4 on the stored Stage 3 result of a run and print what it finds (replaces run_stage4_demo.py for the new code).

  python scripts/stage4_on_stored.py --query-id <uuid> [--sq 1 3] [--write] [--out reports/x.json]

Reads the digests of the newest Stage 3 run of each sub-question, then: claims -> clusters -> support -> conflicts -> labels. Without --write
nothing is stored. Judge answers are cached (.cache/stage4_judge), so a second run of the same input costs no LLM calls.
"""
import argparse
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
from apps.api.graph.nodes import factcheck_node  # noqa: E402
from apps.api.services import db_service  # noqa: E402
from apps.api.services.db_service import supabase  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query-id", required=True)
    ap.add_argument("--sq", type=int, nargs="*", help="1-based sub-question numbers (default all)")
    ap.add_argument("--write", action="store_true", help="store fact_claims / contradictions (replaces the stored result of this run)")
    ap.add_argument("--out")
    args = ap.parse_args()

    sqs = sorted(supabase.table("sub_questions").select("id,main_topic,created_at").eq("query_id", args.query_id).execute().data, key=lambda r: r["created_at"])
    out, all_claims, all_dis = [], [], []
    t_all = time.time()
    for si, sq in enumerate(sqs, 1):
        if args.sq and si not in args.sq:
            continue
        t0 = time.time()
        steps = []
        report = lambda step, message, **data: steps.append((step, round(time.time() - t0, 1)))   # noqa: E731
        labeled, disagreements, summary = factcheck_node._check_sub_question(args.query_id, SimpleNamespace(id=sq["id"], main_topic=sq["main_topic"]), report)
        all_claims += labeled
        all_dis += disagreements
        print(f"\nSQ{si} {sq['main_topic'][:80]}  ({time.time() - t0:.0f}s)")
        print(f"   digests {summary['digests']}, claims {summary['claims_loaded']} -> {summary['total']} checked: supported {summary['supported']}, "
              f"unverified {summary['unverified']}, contradicted {summary['contradicted']}, contested {summary['contested']}, disagreements {summary['disagreements']}")
        print("   steps (seconds since start):", steps)
        for r in sorted(labeled, key=lambda r: ({"contradicted": 0, "supported": 1, "unverified": 2}[r["label"]], -r["confidence"])):
            docs = sorted({e["source_title"][:40] for e in r["evidence"] if e["relation"] == "supports"})
            print(f"   [{r['label']:<12}] conf={r['confidence']:.2f} docs={r['support_doc_count']}/{r['contra_doc_count']}  {r['claim'][:110]}" + (f"  <= {docs}" if r["label"] == "supported" else ""))
        for d in disagreements:
            print(f"   DISAGREE: A: {d['claim_a'][:90]}\n             B: {d['claim_b'][:90]}\n             why: {d['reason'][:140]}")
        out.append({"sub_question": sq["main_topic"], "summary": summary, "claims": labeled, "disagreements": disagreements})
    print(f"\ntotal {time.time() - t_all:.0f}s; claims {len(all_claims)}, disagreements {len(all_dis)}")
    if args.write:
        db_service.write_fact_claims(args.query_id, all_claims)
        db_service.write_contradictions(args.query_id, all_dis)
        print("stored")
    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
