import logging
import os

from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder
from apps.api.agents.stage4_factcheck.common import nli_probs
from apps.api.agents.stage4_factcheck.judge import judge_conflict, run_parallel

logger = logging.getLogger("apps.api.agents.stage4_factcheck")

QUOTE_CLAIM_SIM = 0.70   # placeholder, tune on the eval set
CONTRADICT_MIN = 0.70    # NLI is only a prefilter; the judge makes the final call
JUDGE_MIN = 0.70         # judge confidence needed to keep a conflict
MAX_PAIRS = int(os.getenv("STAGE4_MAX_PAIRS", "200"))    # cap NLI calls per sub-question, most similar pairs first
MAX_JUDGE = int(os.getenv("STAGE4_MAX_JUDGE", "40"))     # cap judge calls per sub-question


def detect(clusters: list[dict]) -> tuple[dict[int, list[dict]], list[dict]]:
    """Returns:
    conflicts      {cluster_idx: [evidence from OTHER clusters that contradict its claim]}
    disagreements  flat list for the report's 'Contested' callouts"""
    sup = [m for c in clusters for m in c.get("support", [])]
    if sup:
        embs = get_embedder().encode([m["quote"] for m in sup], normalize_embeddings=True)
        for m, e in zip(sup, embs):
            m["q_emb"] = e

    # gate 1: the other source's quote must be about the same thing as this claim
    cands = []
    for i, a in enumerate(clusters):
        if not a.get("support"):
            continue
        a_docs = {e["doc"] for e in a["support"]}
        for j, b in enumerate(clusters):
            if i == j or not b.get("support"):
                continue
            for m in b["support"]:
                if m["doc"] in a_docs:      # a document supporting A cannot also contradict A
                    continue
                sim = float(m["q_emb"] @ a["emb"])
                if sim >= QUOTE_CLAIM_SIM:
                    cands.append((sim, i, j, m))
    cands.sort(key=lambda t: t[0], reverse=True)
    if len(cands) > MAX_PAIRS:
        logger.warning("Stage 4: %d quote/claim pairs passed the topic gate; only the %d most similar go to NLI", len(cands), MAX_PAIRS)
    cands = cands[:MAX_PAIRS]

    # gate 2: forward NLI (their quote vs our claim), cheap prefilter only
    fwd = nli_probs([(m["quote"], clusters[i]["claim"]) for _, i, _, m in cands])
    survivors = [(c, p) for c, p in zip(cands, fwd) if p["contradiction"] >= CONTRADICT_MIN]
    survivors.sort(key=lambda t: t[1]["contradiction"], reverse=True)
    if len(survivors) > MAX_JUDGE:
        logger.warning("Stage 4: %d pairs passed the NLI prefilter; only the %d most contradictory go to the conflict judge", len(survivors), MAX_JUDGE)
    survivors = survivors[:MAX_JUDGE]

    # gate 3: LLM judge decides whether it is a real conflict on the same aspect
    conflicts, disagreements, seen = {}, [], set()
    verdicts = run_parallel(judge_conflict, [(clusters[c[1]]["claim"], c[3]["quote"], c[3]["claim"]) for c, _ in survivors])   # results in input order
    for (c, p), v in zip(survivors, verdicts):
        _, i, j, m = c
        if not (v["conflicts"] and v["same_aspect"] and v["confidence"] >= JUDGE_MIN):
            continue
        prob = min(p["contradiction"], v["confidence"])
        conflicts.setdefault(i, []).append(
            {**m, "relation": "contradicts", "prob": prob, "judge_reason": v["reason"]}
        )

        key = tuple(sorted((i, j)))
        if key not in seen:
            seen.add(key)
            rep = clusters[i]["support"][0]
            disagreements.append({
                "claim_a": clusters[i]["claim"], "claim_b": m["claim"],
                "source_a_title": rep["source_title"], "source_b_title": m["source_title"],
                "quote_a": rep["quote"], "quote_b": m["quote"],
                "prob": round(prob, 3), "reason": v["reason"],
            })
    return conflicts, disagreements