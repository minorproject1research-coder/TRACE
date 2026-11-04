#!/usr/bin/env python3
"""
Forced-candidate negative control for the Stage 3 evidence judge.

The older negative control adds an impossible aspect (legal requirements, history before 2000, cloud pricing) but that aspect ends
up with ZERO candidate findings, so the judge is never asked to reject anything. This control forces candidates: for each control
aspect it sends the CANDIDATES_PER_CONTROL (default 6) most similar verified findings of the sub-question to the REAL judge.

PASS only if none of them gets final == "yes". Uses stored digests (no Groq calls, no digest generation) and the real judge
endpoint (JUDGE_URL); if the endpoint is not configured or answers with errors the script exits with ERROR, never PASS.

  python tests/forced_candidate_control.py --query-id <id> [--sub-question-id <id>] [--candidates 6]
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder          # noqa: E402
from apps.api.agents.stage3_summarizer import evidence_judge                         # noqa: E402
from apps.api.agents.stage3_summarizer.chunk_selector import _clean_topic            # noqa: E402
from apps.api.services.db_service import supabase                                    # noqa: E402

CONTROLS = [
    "What are the legal and regulatory requirements for {topic}?",
    "What is the history of {topic} before 2000?",
    "How much does {topic} cost to deploy in cloud pricing terms?",
]
DEFAULT_CANDIDATES = 6


def similar_findings(control_aspect: str, digests: List[Dict], n: int, embedder) -> List[Dict]:
    """The n verified findings most similar to the control aspect, as judge candidates (one per distinct claim)."""
    pool = []
    for d_idx, d in enumerate(digests):
        for f_idx, f in enumerate(d.get("findings", [])):
            if f.get("verified") and f.get("claim") and f.get("quote"):
                pool.append((d_idx, f_idx, d.get("source_id", f"src_{d_idx}"), f))
    if not pool:
        return []
    emb = embedder.encode([control_aspect] + [p[3]["claim"] for p in pool], normalize_embeddings=True)
    sims = emb[1:] @ emb[0]
    order = sorted(range(len(pool)), key=lambda i: float(sims[i]), reverse=True)
    out, seen = [], set()
    for i in order:
        d_idx, f_idx, source_id, f = pool[i]
        key = (source_id, hashlib.sha256(f["claim"].encode()).hexdigest()[:16])
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "aspect_idx": 0, "aspect_text": control_aspect, "source_id": source_id, "claim": f["claim"], "quote": f["quote"],
            "chunk_id": f.get("chunk_id"), "similarity": float(sims[i]), "digest_idx": d_idx, "finding_idx": f_idx,
            "item_id": hashlib.sha256(f"{control_aspect}|{source_id}|{f_idx}".encode()).hexdigest()[:16],
        })
        if len(out) >= n:
            break
    return out


def run_control(sub_question: Dict, digests: List[Dict], template: str, n: int, embedder) -> Dict:
    topic = _clean_topic(sub_question["main_topic"])
    control = template.format(topic=topic)
    candidates = similar_findings(control, digests, n, embedder)
    if not candidates:
        return {"control": control, "status": "NO_FINDINGS", "candidates": 0}
    items = evidence_judge.build_judge_items(candidates, {})          # no chunk text stored with digests: judged without context
    verdicts = evidence_judge.judge_candidates(items)
    rows = []
    for c in candidates:
        key = (0, c["source_id"], hashlib.sha256(c["claim"].encode()).hexdigest()[:16])
        v = (verdicts.get(key) or {}).get("verdict") or {}
        rows.append({"similarity": round(c["similarity"], 3), "claim": c["claim"][:90], "final": v.get("final", "error"),
                     "quote_supports_claim": v.get("quote_supports_claim"), "answers_aspect": v.get("answers_aspect")})
    errors = sum(1 for r in rows if r["final"] not in ("yes", "partial", "no"))
    yes = [r for r in rows if r["final"] == "yes"]
    status = "ERROR" if errors == len(rows) else ("FAIL" if yes else "PASS")
    return {"control": control, "status": status, "candidates": len(rows), "yes": len(yes), "errors": errors, "rows": rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--query-id", required=True)
    ap.add_argument("--sub-question-id")
    ap.add_argument("--candidates", type=int, default=DEFAULT_CANDIDATES)
    ap.add_argument("--out", default="reports/forced_candidate_control.json")
    args = ap.parse_args()

    from dotenv import load_dotenv
    load_dotenv()
    if not evidence_judge._get_config()["JUDGE_URL"]:
        print("ERROR: no judge URL (TRACE_LLM_URL is not set); this control needs the real judge endpoint (no mocks). No verdict given.")
        return 2

    q = supabase.table("sub_questions").select("*").eq("query_id", args.query_id)
    if args.sub_question_id:
        q = q.eq("id", args.sub_question_id)
    sub_questions = q.execute().data
    if not sub_questions:
        print("ERROR: no sub-questions found")
        return 2

    embedder = get_embedder()
    results, rc = [], 0
    for sq in sub_questions:
        digests = supabase.table("digests").select("*").eq("query_id", args.query_id).eq("sub_question_id", sq["id"]).execute().data
        for template in CONTROLS:
            r = run_control(sq, digests, template, args.candidates, embedder)
            r["sub_question_id"] = sq["id"]
            results.append(r)
            print(f"\n[{r['status']}] {sq['id'][:8]} {r['control']}  (candidates={r['candidates']}, yes={r.get('yes', '-')}, errors={r.get('errors', '-')})")
            for row in r.get("rows", []):
                print(f"    {row['final']:<7} sim={row['similarity']:.3f}  {row['claim']}")

    n_pass = sum(r["status"] == "PASS" for r in results)
    n_fail = sum(r["status"] == "FAIL" for r in results)
    n_other = len(results) - n_pass - n_fail
    print(f"\n{'=' * 60}\nControls: {len(results)}  PASS={n_pass}  FAIL={n_fail}  ERROR/NO_FINDINGS={n_other}")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    if n_fail:
        print("RESULT: FAIL - the judge accepted an off-topic finding as 'yes' for a control aspect")
        return 1
    if n_other:
        print("RESULT: INCONCLUSIVE - some controls had no findings or judge errors; no PASS claimed")
        return 2
    print("RESULT: PASS - the judge rejected every forced candidate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
