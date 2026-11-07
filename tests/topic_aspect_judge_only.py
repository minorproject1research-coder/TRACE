"""Experiment for planned item B2: the sub-question as an aspect for the JUDGE ONLY (TOPIC_ASPECT=judge), on the stored runs of Q1 to Q6.

The digests are the stored ones, which were written WITHOUT the topic aspect: exactly the situation of the new mode, so unlike the first
experiment (tests/topic_aspect_experiment.py, 2026-11-05) this one is not biased. The topic aspect gets JUDGE_CANDIDATES_PER_ASPECT candidates
by similarity (select_candidates(..., topic_aspect_idx=0)). Host judge only, no Groq, no database writes, temp verdict cache.

Pre-registered rule (2026-11-07, before the first run):
  (1) the judge returns a verdict for every candidate (no errors), and
  (2) at least 80% of the claims it rates "yes" directly answer the sub-question's question when I read them (LLM label, mine), and
  (3) the digests are unchanged by construction (tests/test_topic_aspect.py::TestJudgeOnlyMode), so findings per digest need no new run.
Reported, not a pass condition: how many stored-sufficient sub-questions are NOT covered on the topic (the aspect's effect on "sufficient").

Output: reports/topic_aspect_judge_only.json and a printed table.
Usage:  python tests/topic_aspect_judge_only.py [query_id ...]
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

RUNS = ["2397750f-41eb-4693-a21e-fd5a7045e9d7",      # Q1 Mamba (17:33)
        "156ebc90-6250-4178-9d80-94b9ecdf50df",      # Q2 mixture of experts (23:29)
        "bf7055b3-a202-4ef6-b47c-9e99c7f7a118",      # Q3 4-bit quantization
        "d76170ee-fc49-4d07-9c4f-a1446bf6ff0c",      # Q4 reasoning benchmarks
        "7d7d1b7e-3c59-4ec6-a076-39c815d4f298",      # Q5 diffusion vs GANs
        "fb587186-7af6-4bea-be1e-dbb0a10936ee"]      # Q6 federated learning


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
            candidates = ej.select_candidates([topic], rows, chunk_lookup, embedder, topic_aspect_idx=0)
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
    (ROOT / "reports" / "topic_aspect_judge_only.json").write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
