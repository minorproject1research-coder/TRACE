#!/usr/bin/env python3
"""
Is Stage 3 reproducible? Runs the real summarizer_node twice on the SAME stored sources of one sub-question and compares the results.
DRY RUN: nothing is written to the database (write_digests / write_coverage are patched out) and the judge cache is a temp file.

Modes (each = two runs, compared):
  default   cache OFF, temperature 0.1, no seed        (what the pipeline did so far)
  seeded    cache OFF, temperature 0,   seed 7         (does sampling alone make reruns identical?)
  cached    cache ON  (first run cold, second run hits) (what the pipeline does now)

Uses the real Groq digest model and the real judge endpoint: about 2 x (jobs) Groq calls per mode, jobs = papers + web sources.
Defaults to 3 papers + 1 web source to keep quota use small (set --papers/--web to change).

  python tests/stage3_reproducibility.py --query-id <id> --sub-question-id <id> [--modes default,seeded,cached]
"""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from apps.api.agents.stage3_summarizer import digest_generator, evidence_judge  # noqa: E402
from apps.api.graph.nodes import summarizer_node as sn  # noqa: E402
from apps.api.graph.state import SharedResearchState  # noqa: E402
from apps.api.models.task_plan import SubQuestion, TaskPlan  # noqa: E402
from apps.api.services import db_service  # noqa: E402
from apps.api.services.db_service import supabase  # noqa: E402


def run_once(query, sq) -> dict:
    plan = TaskPlan(query_id=query["id"], raw_query=query["raw_query"],
                    sub_questions=[SubQuestion(id=sq["id"], main_topic=sq["main_topic"], detail_questions=sq["detail_questions"])])
    return sn.summarizer_node(SharedResearchState(raw_query=query["raw_query"], task_plan=plan))


def view(result: dict, sq_id: str) -> dict:
    """The parts of a run that must not change between reruns."""
    findings = {}
    for d in result["digests"]:
        findings[d["source_id"]] = sorted((f["claim"], f["quote"], f["verified"]) for f in d["findings"])
    cov = result["coverage"][sq_id]
    return {
        "findings": findings,
        "sufficient": cov["sufficient"],
        "uncovered_details": sorted(cov["uncovered_details"]),
        "uncovered_aspects": sorted(cov.get("uncovered_aspects", [])),
        "unjudged_aspects": sorted(cov.get("unjudged_aspects", [])),
        "judge_used": cov.get("judge_used"),
        "judge_stats": cov.get("judge_stats"),
        "aspect_evidence": {str(k): sorted((e["source_id"], e["claim_prefix"]) for e in v) for k, v in (cov.get("aspect_evidence") or {}).items()},
    }


def compare(a: dict, b: dict) -> dict:
    claims_a = {(s, c) for s, fs in a["findings"].items() for c, _, _ in fs}
    claims_b = {(s, c) for s, fs in b["findings"].items() for c, _, _ in fs}
    union = claims_a | claims_b
    same_cov = all(a[k] == b[k] for k in ("sufficient", "uncovered_details", "uncovered_aspects", "unjudged_aspects", "judge_stats", "aspect_evidence"))
    return {
        "findings_run1": len(claims_a), "findings_run2": len(claims_b),
        "findings_in_both": len(claims_a & claims_b), "findings_identical_sets": a["findings"] == b["findings"],
        "claim_overlap_pct": round(100 * len(claims_a & claims_b) / len(union), 1) if union else 100.0,
        "coverage_identical": same_cov,
        "yes_run1_run2": (a["judge_stats"]["yes"], b["judge_stats"]["yes"]),
        "uncovered_aspects_run1": a["uncovered_aspects"], "uncovered_aspects_run2": b["uncovered_aspects"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query-id", required=True)
    ap.add_argument("--sub-question-id", required=True)
    ap.add_argument("--modes", default="default,seeded,cached")
    ap.add_argument("--papers", type=int, default=3)
    ap.add_argument("--web", type=int, default=1)
    ap.add_argument("--out", default="reports/stage3_reproducibility.json")
    args = ap.parse_args()

    query = supabase.table("research_queries").select("*").eq("id", args.query_id).execute().data[0]
    sq = supabase.table("sub_questions").select("*").eq("query_id", args.query_id).eq("id", args.sub_question_id).execute().data[0]

    # dry run: no DB writes, temp judge cache, small source set
    db_service.write_digests = lambda rows: None
    db_service.write_coverage = lambda rows: None
    sn.MAX_PAPERS, sn.MAX_WEB = args.papers, args.web
    tmp = tempfile.mkdtemp(prefix="stage3_repro_")
    report = {"query_id": args.query_id, "sub_question_id": args.sub_question_id, "papers": args.papers, "web": args.web,
              "digest_model": sn.llm_service.MODEL_NAME, "modes": {}}
    print(f"DRY RUN (no database writes). {args.papers} papers + {args.web} web source(s); digest model {report['digest_model']}")

    for mode in [m.strip() for m in args.modes.split(",") if m.strip()]:
        os.environ["DIGEST_CACHE_DIR"] = str(Path(tmp) / f"digest_{mode}")        # a fresh cache per mode
        if mode == "default":
            os.environ["DIGEST_CACHE"] = "false"
            digest_generator.DIGEST_TEMPERATURE, digest_generator.DIGEST_SEED = 0.1, None
        elif mode == "seeded":
            os.environ["DIGEST_CACHE"] = "false"
            digest_generator.DIGEST_TEMPERATURE, digest_generator.DIGEST_SEED = 0.0, 7
        elif mode == "cached":
            os.environ["DIGEST_CACHE"] = "true"
            digest_generator.DIGEST_TEMPERATURE, digest_generator.DIGEST_SEED = 0.1, None
        else:
            print(f"unknown mode {mode}")
            continue
        evidence_judge.JUDGE_CACHE_PATH = Path(tmp) / f"judge_{mode}.json"            # each mode judges from scratch
        print(f"\n--- mode {mode}: run 1 ...")
        r1 = view(run_once(query, sq), sq["id"])
        evidence_judge.JUDGE_CACHE_PATH = Path(tmp) / f"judge_{mode}_run2.json"       # judge run 2 from scratch too (tests judge determinism)
        print(f"--- mode {mode}: run 2 ...")
        r2 = view(run_once(query, sq), sq["id"])
        result = compare(r1, r2)
        report["modes"][mode] = result
        print(json.dumps(result, indent=2, ensure_ascii=False))

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n" + "=" * 60)
    for mode, r in report["modes"].items():
        print(f"{mode:<8} coverage identical: {r['coverage_identical']!s:<5}  findings identical: {r['findings_identical_sets']!s:<5} "
              f"overlap {r['claim_overlap_pct']}%  yes {r['yes_run1_run2']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
