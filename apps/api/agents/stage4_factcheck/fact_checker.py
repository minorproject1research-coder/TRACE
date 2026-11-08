import logging
import os

from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder
from apps.api.agents.stage4_factcheck.common import nli_probs, doc_key
from apps.api.agents.stage4_factcheck.judge import judge_support, judge_same_claim, judge_near_match, run_parallel

logger = logging.getLogger("apps.api.agents.stage4_factcheck")

try:
    from apps.api.agents.stage3_summarizer.coverage_check import EVIDENCE_WEIGHT
except ImportError:
    EVIDENCE_WEIGHT = {"full_text": 1.0, "abstract": 0.5, "web_snippet": 0.5}

# Checked on tests/stage4_eval.py (30 labeled pairs, 9 of them the same claim): the same-claim pairs had cosine 0.86 to 0.97, and a pair of DIFFERENT
# claims scored 0.957 ("degrades accuracy more for smaller models" vs "often causes a noticeable drop in accuracy"), so 0.95 merged a wrong pair
# without asking the judge. Embeddings cannot tell these apart; the judge decides everything but the near-copies.
CLUSTER_CAND_SIM = 0.84      # claims at least this similar are merge candidates (was 0.80: no same-claim pair was below 0.86)
CLUSTER_AUTO_SIM = 0.98      # near-identical wording: merge without asking the judge (was 0.95)
CLUSTER_SIM = CLUSTER_CAND_SIM   # kept so older scripts that print it still work
MAX_MERGE_JUDGE = int(os.getenv("STAGE4_MAX_MERGE_JUDGE", "300"))      # cap judge calls for merging per sub-question

ENTAIL_MIN = 0.50            # NLI entailment needed for a quote to count as support
SUPPORT_JUDGE_MIN = 0.70     # judge confidence needed to accept a quote that NLI rejected
MAX_SUPPORT_JUDGE = int(os.getenv("STAGE4_MAX_SUPPORT_JUDGE", "150"))  # cap judge calls for support checks per sub-question

MIN_EVIDENCE = 1.5           # "supported" needs this much evidence weight over distinct documents

LABELS = ("supported", "partially_supported", "unverified", "contradicted")
NEAR_ON = os.getenv("STAGE4_NEAR", "true").strip().lower() not in ("0", "false", "no", "off")
NEAR_MIN_SIM = float(os.getenv("STAGE4_NEAR_MIN_SIM", "0.70"))     # a claim of another document must be at least this similar to be asked about
NEAR_CANDIDATES = int(os.getenv("STAGE4_NEAR_CANDIDATES", "1"))   # per claim, most similar first (2 doubles the judge calls for a few more matches)
MAX_NEAR_JUDGE = int(os.getenv("STAGE4_MAX_NEAR_JUDGE", "120"))     # cap judge calls for near matches per sub-question


def _stage3_supports(finding: dict) -> bool:
    """Stage 3's independent judge (judge-v2, with the surrounding passage) already said "yes, the quote supports the claim" for this finding
    (for some aspect; support of the claim by its own quote does not depend on the aspect)."""
    return any(isinstance(j, dict) and j.get("quote_supports_claim") == "yes" for j in (finding.get("judge") or {}).values())


def load_claims(digests: list[dict]) -> list[dict]:
    claims, seen = [], set()
    for d in digests:
        level = d.get("evidence_level") or "full_text"   # older rows without a level count as full text
        ev = EVIDENCE_WEIGHT.get(level, 1.0)
        rel = float(d["reliability"])
        for f in d["findings"] or []:
            if not f.get("verified") or f.get("grounded") is False:
                continue
            if not f.get("claim") or not f.get("quote"):
                continue
            key = (str(d["source_id"]), " ".join(f["claim"].lower().split()))
            if key in seen:                  # Loop 2 may read the same source again and find the same statement: it counts once
                continue
            seen.add(key)
            claims.append({
                "claim": f["claim"],
                "quote": f["quote"],
                "source_id": str(d["source_id"]),
                "source_title": d["source_title"],
                "doc": doc_key(d["source_title"], d["source_id"]),
                "reliability": rel,
                "evidence_level": level,
                "ev": ev,
                "weight": round(rel * ev, 3),
                "stage3_support": _stage3_supports(f),
            })
    return claims


def build_clusters(claims: list[dict]) -> list[dict]:
    """Greedy clustering, strongest claim first. Embeddings propose merges, the judge confirms.

    The result is the same as asking the judge one candidate at a time: the (up to 3) candidate clusters of a claim are judged side by side
    and then looked at in order, the first one that is the same claim wins, and the budget is charged only for the candidates that the
    sequential version would have asked about. A representative claim never changes, so a judged pair does not depend on thread order."""
    if not claims:
        return []
    emb = get_embedder().encode([c["claim"] for c in claims], normalize_embeddings=True)
    order = sorted(range(len(claims)), key=lambda i: claims[i]["weight"], reverse=True)

    clusters, budget, skipped_for_budget = [], MAX_MERGE_JUDGE, 0
    for i in order:
        cands = sorted(((float(emb[i] @ c["emb"]), k) for k, c in enumerate(clusters)), reverse=True)
        cands = [(s, k) for s, k in cands if s >= CLUSTER_CAND_SIM][:3]

        # which candidates need the judge (an auto-merge before them makes the later ones irrelevant)
        ask = []
        for s, k in cands:
            if s >= CLUSTER_AUTO_SIM:
                break
            if claims[i]["doc"] in {m["doc"] for m in clusters[k]["members"]}:
                continue                  # same document adds no new support, so no judge call
            ask.append(k)
        answers = dict(zip(ask, run_parallel(judge_same_claim, [(clusters[k]["claim"], claims[i]["claim"]) for k in ask])))

        placed = False
        for s, k in cands:
            c = clusters[k]
            if s >= CLUSTER_AUTO_SIM:
                same = True
            elif claims[i]["doc"] in {m["doc"] for m in c["members"]}:
                same = False
            elif budget > 0:
                budget -= 1
                same = answers.get(k, False)
            else:
                same = False
                skipped_for_budget += 1
            if same:
                c["members"].append(claims[i])
                placed = True
                break
        if not placed:
            clusters.append({"claim": claims[i]["claim"], "emb": emb[i], "members": [claims[i]]})
    if skipped_for_budget:
        logger.warning("Stage 4: the merge judge budget (%d) ran out; %d candidate pair(s) were not judged and stay separate clusters",
                       MAX_MERGE_JUDGE, skipped_for_budget)
    return clusters


def verify_support(clusters: list[dict]) -> list[dict]:
    """A member counts as support when its quote supports its OWN claim.
    The merge step already confirmed that its claim states the same proposition as the cluster's.
    NLI is the fast path; quotes NLI does not accept are re-checked by the judge (calls run side by side; the budget is charged in the
    order the members are met, so which members get a re-check does not depend on timing)."""
    # members whose quote the Stage 3 judge already found to support the claim need neither NLI nor a Groq call
    pending = [m for c in clusters for m in c["members"] if not m.get("stage3_support")]
    probs = iter(nli_probs([(m["quote"], m["claim"]) for m in pending]))
    ACCEPTED = {"entailment": 1.0, "contradiction": 0.0, "neutral": 0.0, "stage3": True}
    scored = [[(m, ACCEPTED if m.get("stage3_support") else next(probs)) for m in c["members"]] for c in clusters]

    budget, asks, skipped = MAX_SUPPORT_JUDGE, [], 0
    for ci, members in enumerate(scored):
        for mi, (m, p) in enumerate(members):
            if p["entailment"] < ENTAIL_MIN and p["contradiction"] < 0.5:
                if budget > 0:
                    budget -= 1
                    asks.append((ci, mi))
                else:
                    skipped += 1
    answers = dict(zip(asks, run_parallel(judge_support, [(scored[ci][mi][0]["claim"], scored[ci][mi][0]["quote"]) for ci, mi in asks])))
    for ci, (c, members) in enumerate(zip(clusters, scored)):
        support = []
        for mi, (m, p) in enumerate(members):
            if p.get("stage3"):
                support.append({**m, "relation": "supports", "prob": 0.95, "via": "stage3_judge"})
            elif p["entailment"] >= ENTAIL_MIN:
                support.append({**m, "relation": "supports", "prob": p["entailment"]})
            elif (ci, mi) in answers:
                v = answers[(ci, mi)]
                if v["supports"] and v["confidence"] >= SUPPORT_JUDGE_MIN:
                    support.append({**m, "relation": "supports", "prob": v["confidence"]})
        c["support"] = support
    if skipped:
        logger.warning("Stage 4: the support judge budget (%d) ran out; %d quote(s) NLI did not accept were not re-checked and do not count as support",
                       MAX_SUPPORT_JUDGE, skipped)
    return clusters


def find_near_matches(clusters: list[dict]) -> list[dict]:
    """For a claim that rests on ONE document: does another document state a close variant of it (not the same claim, which the merge step
    already looked for)? Candidates are the most similar claims of other documents that have a quote supporting them; the judge decides,
    side by side for the (up to 2) candidates of a claim, and the first yes wins. A yes is stored in cluster["near"]; the label step turns it
    into `partially_supported`. The budget is charged in cluster order, so which claims get asked about does not depend on thread timing."""
    if not NEAR_ON:
        return clusters
    import numpy as np

    live = [ci for ci, c in enumerate(clusters) if c.get("support")]
    if len(live) < 2:
        return clusters
    emb = np.stack([clusters[ci]["emb"] for ci in live])
    sims = emb @ emb.T
    jobs, budget, skipped = [], MAX_NEAR_JUDGE, 0
    for a, ci in enumerate(live):
        c = clusters[ci]
        own_docs = {m["doc"] for m in _distinct_docs(c["support"])}
        if len(own_docs) != 1:
            continue                                        # two documents already: supported or a conflict, not a near match
        cands = []
        for b in sorted(range(len(live)), key=lambda j: -sims[a, j]):
            if b == a or sims[a, b] < NEAR_MIN_SIM:
                continue
            other = clusters[live[b]]
            best = max((s for s in _distinct_docs(other["support"]) if s["doc"] not in own_docs), key=lambda s: s["weight"], default=None)
            if best is not None:
                cands.append((float(sims[a, b]), live[b], best))
            if len(cands) == NEAR_CANDIDATES:
                break
        for _, oi, best in cands:
            if budget > 0:
                budget -= 1
                jobs.append((ci, oi, best))
            else:
                skipped += 1
    answers = run_parallel(judge_near_match, [(clusters[ci]["claim"], clusters[oi]["claim"], best["quote"]) for ci, oi, best in jobs])
    for (ci, oi, best), yes in zip(jobs, answers):          # jobs are in cluster order, so the first yes of a claim is its most similar candidate
        if yes and "near" not in clusters[ci]:
            clusters[ci]["near"] = {k: best.get(k) for k in ("source_id", "source_title", "quote", "reliability", "evidence_level", "ev", "weight", "doc")} | {
                "relation": "near_match", "via": "near_judge", "near_claim": clusters[oi]["claim"], "prob": 0.0}
    if skipped:
        logger.warning("Stage 4: the near-match judge budget (%d) ran out; %d candidate pair(s) were not judged", MAX_NEAR_JUDGE, skipped)
    return clusters


def _distinct_docs(items: list[dict]) -> list[dict]:
    best = {}
    for it in items:
        if it["doc"] not in best or it["weight"] > best[it["doc"]]["weight"]:
            best[it["doc"]] = it
    return list(best.values())


def _noisy_or(items: list[dict]) -> float:
    p = 1.0
    for it in items:
        p *= 1 - min(max(it["weight"], 0.0), 0.95)
    return round(1 - p, 3)


def label_clusters(clusters: list[dict], conflicts: dict[int, list[dict]]) -> list[dict]:
    rows = []
    for ci, c in enumerate(clusters):
        sup = _distinct_docs(c["support"])
        if not sup:
            continue          # no quote supports this claim (claim drift): drop it
        con = _distinct_docs(conflicts.get(ci, []))

        s, k = _noisy_or(sup), _noisy_or(con)
        ev_total = sum(e["ev"] for e in sup)

        if con and k >= s:
            label, conf = "contradicted", k
        elif len(sup) >= 2 and ev_total >= MIN_EVIDENCE:
            label, conf = "supported", s
        elif c.get("near") and len(sup) == 1:
            label, conf = "partially_supported", min(_noisy_or(sup + [c["near"]]), 0.6)
        else:
            label, conf = "unverified", min(s, 0.5)

        near = [c["near"]] if label == "partially_supported" else []
        rows.append({
            "claim": c["claim"],
            "label": label,
            "confidence": conf,
            "support_doc_count": len(sup),
            "contra_doc_count": len(con),
            "contested": bool(con) and label != "contradicted",
            "evidence": [
                {"source_id": e["source_id"], "source_title": e["source_title"], "quote": e["quote"],
                 "relation": e["relation"], "reliability": e["reliability"],
                 "evidence_level": e["evidence_level"], "prob": round(e["prob"], 3), "via": e.get("via"),
                 **({"near_claim": e["near_claim"]} if e.get("near_claim") else {})}
                for e in sup + con + near
            ],
        })
    return rows