"""Step 1: retrieve candidate papers per sub-question and sample a spread of
similarity levels (hard negatives included). No PDF parsing happens here.

Run from the repo root:  python -m evaluation.relevance_judge.collect_candidates
Resumable: raw retrieval results are cached in raw/<sub_question_id>.json.
"""
import argparse
import asyncio
import json
import logging
import random
from pathlib import Path

from apps.api.agents.stage1_planner import query_expansion
from apps.api.agents.stage2_retrieval.paper_retrieval_agent import PaperRetrievalAgent
from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("relevance_judge.collect")

HERE = Path(__file__).parent
RAW_DIR = HERE / "raw"
SEED = 42

# Share of each sub-question's sample drawn from similarity tiers (top/mid/low).
# Mid and low tiers supply the borderline cases and hard negatives.
TIER_SPLIT = (0.42, 0.33, 0.25)


def sample_spread(papers: list[dict], n: int, rng: random.Random) -> list[dict]:
    ranked = sorted(papers, key=lambda p: p["embedding_similarity"], reverse=True)
    if len(ranked) <= n:
        return ranked
    third = len(ranked) / 3
    tiers = [ranked[: int(third)], ranked[int(third): int(2 * third)], ranked[int(2 * third):]]
    quotas = [round(n * s) for s in TIER_SPLIT]
    quotas[0] += n - sum(quotas)
    picked = []
    for tier, quota in zip(tiers, quotas):
        picked.extend(rng.sample(tier, min(quota, len(tier))))
    leftovers = [p for p in ranked if p not in picked]
    rng.shuffle(leftovers)
    picked.extend(leftovers[: n - len(picked)])
    return picked


async def retrieve_one(agent: PaperRetrievalAgent, sq: dict) -> list[dict]:
    cache = RAW_DIR / f"{sq['id']}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    queries = query_expansion.expand(sq["main_topic"], sq["detail_questions"])
    papers = await agent.retrieve(sq["main_topic"], queries)
    cache.write_text(json.dumps(papers, ensure_ascii=False), encoding="utf-8")
    return papers


async def main(per_question: int, only: list[str] | None):
    RAW_DIR.mkdir(exist_ok=True)
    sub_questions = json.loads((HERE / "sub_questions.json").read_text(encoding="utf-8"))
    if only:
        sub_questions = [s for s in sub_questions if s["id"] in only]

    agent = PaperRetrievalAgent(max_results_per_query=10)
    embedder = get_embedder()
    rng = random.Random(SEED)
    rows = []

    for sq in sub_questions:
        try:
            papers = await retrieve_one(agent, sq)
        except Exception as e:
            log.error("Retrieval failed for %s: %s", sq["id"], e)
            continue

        papers = [p for p in papers if (p.get("abstract") or "").strip() and len(p["abstract"]) > 200]
        if not papers:
            log.warning("%s: no papers with usable abstracts", sq["id"])
            continue

        q_emb = embedder.encode([sq["main_topic"]], normalize_embeddings=True)[0]
        d_emb = embedder.encode([p["abstract"] for p in papers], normalize_embeddings=True)
        for p, sim in zip(papers, d_emb @ q_emb):
            p["embedding_similarity"] = float(round(sim, 4))

        chosen = sample_spread(papers, per_question, rng)
        log.info("%s: %d usable -> sampled %d", sq["id"], len(papers), len(chosen))
        for i, p in enumerate(chosen):
            rows.append({
                "id": f"{sq['id']}_{i:02d}",
                "sub_question_id": sq["id"],
                "sub_question": sq["main_topic"],
                "title": p["title"],
                "abstract": p["abstract"],
                "year": p.get("year"),
                "source": p.get("source"),
                "doi": p.get("doi"),
                "arxiv_id": p.get("arxiv_id"),
                "embedding_similarity": p["embedding_similarity"],
            })

    out = HERE / "candidates.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    log.info("Wrote %d candidate rows to %s", len(rows), out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-question", type=int, default=12)
    ap.add_argument("--only", nargs="*", help="sub-question ids, e.g. sq01 sq02")
    args = ap.parse_args()
    asyncio.run(main(args.per_question, args.only))
