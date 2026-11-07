"""Run Loop 2 on the stored Stage 3 result of a finished run, without changing that run (planned items A2 and A4).

What it does for every sub-question of the run:
  1. rebuilds the Stage 3 situation from the database (aspects, digests, the papers that were read, the passages their quotes came from);
  2. judges the stored digests again with the CURRENT judge (a fresh baseline: the judge is not exactly deterministic, so "covered before"
     is measured the same way as "covered after");
  3. runs Loop 2 (apps/api/agents/stage3_summarizer/loop2.py) with the steps and triage given on the command line;
  4. prints and stores what each step added and which aspects it covered.

Dry run: the new papers and web pages of the queries step are counted but NOT stored (stored runs stay as they were); the pool step parses
pool papers, which only fills the parse cache. Real Groq digests and judge calls, a temporary judge cache (reports/judge_cache.json is not
touched).

  python scripts/loop2_on_stored.py --query-id <uuid> [--sq 3 4] [--steps reselect,pool] [--triage r1|all] [--out reports/x.json]
"""
import argparse
import hashlib
import json
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
import os  # noqa: E402

import audit_tag_precision as at  # noqa: E402
from apps.api.agents.stage1_planner import domain_anchor  # noqa: E402
from apps.api.agents.stage3_summarizer import chunk_selector, coverage_check, detail_aspects, evidence_judge as ej, loop2  # noqa: E402
from apps.api.services import db_service  # noqa: E402
from apps.api.services.db_service import supabase  # noqa: E402


def retry(fn, tries=5):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:                       # a dropped connection: try again
            if i == tries - 1:
                raise
            print("  (database read failed, again)", type(e).__name__, file=sys.stderr)
            time.sleep(1.5)


def h(claim):
    return hashlib.sha256(claim.encode()).hexdigest()[:16]


def stored_verdicts(rows, n_aspects):
    """Rebuild judge candidates / verdicts from the 'judge' dicts stored in the findings (only used to show the stored state)."""
    out = {}
    for r in rows:
        for f in r.get("findings") or []:
            for k, v in (f.get("judge") or {}).items():
                if isinstance(v, dict) and v.get("final") in ("yes", "partial", "no") and int(k) < n_aspects:
                    out[(int(k), str(r["source_id"]), h(f["claim"]))] = {"verdict": {"final": v["final"]}}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query-id", required=True)
    ap.add_argument("--sq", type=int, nargs="*", help="1-based sub-question numbers (default all)")
    ap.add_argument("--steps")
    ap.add_argument("--triage")
    ap.add_argument("--out")
    args = ap.parse_args()
    if args.steps:
        os.environ["LOOP2_STEPS"] = args.steps
    if args.triage:
        os.environ["LOOP2_TRIAGE"] = args.triage
    os.environ["LOOP2"] = "true"
    ej.JUDGE_CACHE_PATH = Path(tempfile.mkdtemp()) / "judge_cache.json"

    qid = args.query_id
    rq = retry(lambda: supabase.table("research_queries").select("*").eq("id", qid).execute().data)[0]
    sqs = sorted(retry(lambda: supabase.table("sub_questions").select("*").eq("query_id", qid).execute().data), key=lambda r: r["created_at"])
    covs = {c["sub_question_id"]: c for c in at.latest_generation(retry(lambda: supabase.table("coverage_results").select("*").eq("query_id", qid).execute().data))}
    anchor = domain_anchor.generate(rq["raw_query"])
    max_papers = int(os.getenv("MAX_PAPERS") or 3)
    svc = loop2.Services()
    svc.can_store = False
    report = []
    deadline = time.monotonic() + loop2.time_budget() * 4
    for si, sq in enumerate(sqs, 1):
        if args.sq and si not in args.sq:
            continue
        stored_cov = covs.get(sq["id"], {})
        topic_on = detail_aspects.run_topic_aspect(stored_cov)
        cleaned = chunk_selector._clean_topic(sq["main_topic"])
        digest_aspects, a2d = detail_aspects.flatten_aspects(sq["detail_questions"], sq["id"], cleaned, merge_mode=detail_aspects.run_merge_mode(stored_cov))
        aspects, a2d, details = detail_aspects.with_topic_aspect(digest_aspects, a2d, sq["detail_questions"], sq["main_topic"], enabled=topic_on)
        rows = at.latest_generation([d for d in retry(lambda: supabase.table("digests").select("*").eq("sub_question_id", sq["id"]).execute().data)])
        for r in rows:
            if isinstance(r.get("findings"), str):
                r["findings"] = json.loads(r["findings"])
            for f in r["findings"]:
                f.pop("judge", None)                  # the baseline judges them again
        read_ids = {str(r["source_id"]) for r in rows}
        papers = [p for p in retry(lambda: db_service.get_papers_for_stage3(qid, sq["id"])) if str(p["id"]) in read_ids]
        webs = {str(w["id"]): w for w in retry(lambda: supabase.table("web_sources").select("*").eq("sub_question_id", sq["id"]).execute().data)}
        lookup = {}
        by_id = {str(p["id"]): p for p in papers}
        for r in rows:
            for f in r["findings"]:
                cid = f.get("chunk_id")
                if isinstance(cid, int):
                    src = by_id.get(str(r["source_id"]))
                    if src is not None:
                        chunks = chunk_selector.build_chunks(src)
                        lookup[f"{r['source_id']}:{cid}"] = chunks[cid] if 0 <= cid < len(chunks) else ""
                    elif str(r["source_id"]) in webs:
                        lookup[f"{r['source_id']}:{cid}"] = webs[str(r["source_id"])].get("snippet") or ""
        ctx = loop2.SubQuestionContext(
            query_id=qid, sq=type("SQ", (), {"id": sq["id"], "main_topic": sq["main_topic"], "queries": [], "detail_questions": sq["detail_questions"]})(),
            aspects=aspects, aspect_to_detail=a2d, details_for_coverage=details, digest_aspects=digest_aspects, rows=rows, chunk_lookup=lookup,
            papers=papers, topic_aspect_idx=len(aspects) - 1 if topic_on and len(aspects) > len(digest_aspects) else None,
            anchor=anchor.anchor, context=anchor.context)
        ctx.tried_queries = [q["query_text"] for q in retry(lambda: supabase.table("queries").select("query_text").eq("sub_question_id", sq["id"]).execute().data)]
        pool = svc.pool_rows(qid, sq["id"])
        ctx.paper_keys = {db_service.paper_key(r) for r in pool}
        ctx.web_urls = {w.get("url") for w in webs.values()}

        t0 = time.monotonic()
        candidates, verdicts = svc.judge(ctx)
        cov0 = coverage_check.check_coverage_judged(aspects, a2d, details, rows, verdicts, candidates=candidates)
        base_n = len(rows)
        cov1, cand1, ver1, info = loop2.run_subquestion(ctx, cov0, candidates, verdicts, svc, deadline)
        unc0, unc1 = set(cov0["uncovered_aspects"]), set(cov1["uncovered_aspects"])
        print(f"\nSQ{si} {sq['main_topic'][:70]}\n  aspects {len(aspects)}; uncovered before {len(unc0)} -> after {len(unc1)}; sufficient {cov0['sufficient']} -> {cov1['sufficient']};"
              f" sources {base_n} -> {len(ctx.rows)}; {time.monotonic() - t0:.0f}s")
        if info.get("skipped"):
            print("    Loop 2 skipped:", info["skipped"])
        else:
            print(f"    sufficient: stored/baseline {cov0['sufficient']} -> core {info['sufficient']} (strict {info['sufficient_strict']}); covered by synthesis {info['covered_by_synthesis']}; "
                  f"known gaps without evidence {len(info['known_gaps_no_evidence'])}")
        for text, a in info["aspects"].items():
            print(f"    [{a['status']:<26}] {text[:78]}  before={a.get('before')} steps={a['steps']} covered_by={a['covered_by']} how={a.get('how')} after={a.get('after')}")
        for s in info["steps"]:
            print(f"    step {s['step']:<9} aspects {len(s['aspects'])} -> new sources {s['new_sources']}, verified findings {s['new_verified']}, covered {len(s['covered'])}"
                  f" ({s['seconds']}s) " + " ".join(f"{k}={v}" for k, v in s.items() if k in ("sources_tried", "parsed", "queries", "new_papers_found", "new_web_found", "note", "error")))
        report.append({"sub_question": sq["main_topic"], "aspects": len(aspects), "uncovered_before": sorted(unc0), "uncovered_after": sorted(unc1),
                       "sufficient_before": cov0["sufficient"], "sufficient_after": cov1["sufficient"], "loop2": info})
    out = Path(args.out) if args.out else ROOT / "reports" / f"loop2_stored_{qid[:8]}.json"
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print("\nwritten", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
