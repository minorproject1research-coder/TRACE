"""Experiment: judge each sub-question's own topic as an extra aspect, on stored runs (host judge only, no Groq, no database writes).

Why: the aspects come from the planner's detail questions, which are generic ("advantages and disadvantages", "benefits", "challenges"). The
sub-question itself ("What is a mixture of experts model?") is never judged, so a sub-question is "sufficient" without its own question being
answered (Q2, 2026-11-05). This script takes the stored digests of a run, selects and judges candidates for the topic as if it were an aspect,
and reports whether it would be covered and what the judge accepted.

Pre-registered rule (2026-11-05, before the first run): the topic aspect is adopted if
  (1) the judge returns a verdict for every candidate (no errors) and
  (2) at least 80% of the claims it rates "yes" directly answer the sub-question's topic when I read them (LLM label, mine), and
  (3) at least one sub-question of the 10 changes from covered to uncovered or the reverse for a reason I can see in the claims
      (otherwise the aspect changes nothing and is not worth the extra judge pairs).
Output: reports/topic_aspect_experiment.json and a printed table; verdict cache in a temp file so reports/judge_cache.json is untouched.

Usage:  python tests/topic_aspect_experiment.py [query_id ...]
"""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
import audit_tag_precision as at  # noqa: E402
from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder  # noqa: E402
from apps.api.agents.stage3_summarizer import chunk_selector, coverage_check as cc, evidence_judge as ej  # noqa: E402
from apps.api.services import db_service  # noqa: E402
from apps.api.services.db_service import supabase  # noqa: E402

RUNS = ["cc81e9cc-1bfd-48d1-a3cc-ed23e8c00320",      # Q2, mixture of experts (20:53)
        "2397750f-41eb-4693-a21e-fd5a7045e9d7"]      # Q1, Mamba (17:33)


def source_text(sources, source_id, chunk_id):
    kind, obj = sources.get(source_id, (None, None))
    if kind == "paper":
        chunks = chunk_selector.build_chunks(obj)
        return chunks[chunk_id] if isinstance(chunk_id, int) and 0 <= chunk_id < len(chunks) else ""
    if kind == "web":
        return obj.get("snippet") or ""
    return ""


def main() -> int:
    ej.JUDGE_CACHE_PATH = Path(tempfile.mkdtemp()) / "judge_cache.json"
    embedder = get_embedder()
    out = []
    for qid in (sys.argv[1:] or RUNS):
        sqs = supabase.table("sub_questions").select("*").eq("query_id", qid).order("created_at").execute().data
        stored_cov = {c["sub_question_id"]: c for c in at.latest_generation(supabase.table("coverage_results").select("*").eq("query_id", qid).execute().data)}
        for sq in sqs:
            rows = at.latest_generation([d for d in supabase.table("digests").select("*").eq("sub_question_id", sq["id"]).execute().data])
            for r in rows:
                if isinstance(r.get("findings"), str):
                    r["findings"] = json.loads(r["findings"])
            sources = {str(p["id"]): ("paper", p) for p in db_service.get_papers_for_stage3(qid, sq["id"])}
            sources.update({str(w["id"]): ("web", w) for w in supabase.table("web_sources").select("*").eq("sub_question_id", sq["id"]).execute().data})
            chunk_lookup = {}
            for r in rows:
                for f in r.get("findings") or []:
                    cid = f.get("chunk_id")
                    if isinstance(cid, int):
                        chunk_lookup[f"{r['source_id']}:{cid}"] = source_text(sources, str(r["source_id"]), cid)
            topic = sq["main_topic"]
            candidates = ej.select_candidates([topic], rows, chunk_lookup, embedder)
            items = ej.build_judge_items(candidates, chunk_lookup)
            verdicts = ej.judge_candidates(items) if items else {}
            cov = cc.check_coverage_judged([topic], [0], [topic], rows, verdicts, candidates=candidates)
            h = lambda claim: hashlib.sha256(claim.encode()).hexdigest()[:16]        # the verdict key uses a hash of the claim
            yes = [(c["source_id"], c["claim"]) for c in candidates
                   if verdicts.get((c["aspect_idx"], c["source_id"], h(c["claim"])), {}).get("verdict", {}).get("final") == "yes"]
            states = {"yes": 0, "partial": 0, "no": 0, "error": 0}
            for v in verdicts.values():
                states[v.get("verdict", {}).get("final", "error")] = states.get(v.get("verdict", {}).get("final", "error"), 0) + 1
            covered = not cov.get("uncovered_aspects")
            print(f"[{qid[:6]}] {topic[:60]:60s} candidates {len(candidates):2d} {states} topic covered: {covered} | stored sufficient: {stored_cov.get(sq['id'], {}).get('sufficient')}")
            out.append({"query_id": qid, "sub_question": topic, "candidates": len(candidates), "verdicts": states, "topic_covered": covered,
                        "stored_sufficient": stored_cov.get(sq["id"], {}).get("sufficient"), "yes_claims": [c for _, c in yes],
                        "aspect_states": cov.get("aspect_states") or cov.get("aspect_evidence")})
    (ROOT / "reports" / "topic_aspect_experiment.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
