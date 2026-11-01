from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder
from apps.api.agents.stage4_factcheck.common import nli_probs, doc_key
from apps.api.agents.stage4_factcheck.judge import judge_support, judge_same_claim

try:
    from apps.api.agents.stage3_summarizer.coverage_check import EVIDENCE_WEIGHT
except ImportError:
    EVIDENCE_WEIGHT = {"full_text": 1.0, "abstract": 0.5, "web_snippet": 0.5}

CLUSTER_CAND_SIM = 0.80      # claims at least this similar are merge candidates
CLUSTER_AUTO_SIM = 0.95      # near-identical wording: merge without asking the judge
CLUSTER_SIM = CLUSTER_CAND_SIM   # kept so older scripts that print it still work
MAX_MERGE_JUDGE = 300        # cap judge calls for merging per sub-question

ENTAIL_MIN = 0.50            # NLI entailment needed for a quote to count as support
SUPPORT_JUDGE_MIN = 0.70     # judge confidence needed to accept a quote that NLI rejected
MAX_SUPPORT_JUDGE = 150      # cap judge calls for support checks per sub-question

MIN_EVIDENCE = 1.5           # "supported" needs this much evidence weight over distinct documents


def load_claims(digests: list[dict]) -> list[dict]:
    claims = []
    for d in digests:
        level = d.get("evidence_level") or "full_text"   # older rows without a level count as full text
        ev = EVIDENCE_WEIGHT.get(level, 1.0)
        rel = float(d["reliability"])
        for f in d["findings"] or []:
            if not f.get("verified") or f.get("grounded") is False:
                continue
            if not f.get("claim") or not f.get("quote"):
                continue
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
            })
    return claims


def build_clusters(claims: list[dict]) -> list[dict]:
    """Greedy clustering, strongest claim first. Embeddings propose merges, the judge confirms."""
    if not claims:
        return []
    emb = get_embedder().encode([c["claim"] for c in claims], normalize_embeddings=True)
    order = sorted(range(len(claims)), key=lambda i: claims[i]["weight"], reverse=True)

    clusters, budget = [], MAX_MERGE_JUDGE
    for i in order:
        cands = sorted(((float(emb[i] @ c["emb"]), k) for k, c in enumerate(clusters)), reverse=True)
        cands = [(s, k) for s, k in cands if s >= CLUSTER_CAND_SIM][:3]

        placed = False
        for s, k in cands:
            c = clusters[k]
            if s >= CLUSTER_AUTO_SIM:
                same = True
            elif claims[i]["doc"] in {m["doc"] for m in c["members"]}:
                same = False      # same document adds no new support, so skip the judge call
            elif budget > 0:
                budget -= 1
                same = judge_same_claim(c["claim"], claims[i]["claim"])
            else:
                same = False
            if same:
                c["members"].append(claims[i])
                placed = True
                break
        if not placed:
            clusters.append({"claim": claims[i]["claim"], "emb": emb[i], "members": [claims[i]]})
    return clusters


def verify_support(clusters: list[dict]) -> list[dict]:
    """A member counts as support when its quote supports its OWN claim.
    The merge step already confirmed that its claim states the same proposition as the cluster's.
    NLI is the fast path; quotes NLI does not accept are re-checked by the judge."""
    budget = MAX_SUPPORT_JUDGE
    for c in clusters:
        probs = nli_probs([(m["quote"], m["claim"]) for m in c["members"]])
        support = []
        for m, p in zip(c["members"], probs):
            if p["entailment"] >= ENTAIL_MIN:
                support.append({**m, "relation": "supports", "prob": p["entailment"]})
            elif p["contradiction"] < 0.5 and budget > 0:
                budget -= 1
                v = judge_support(m["claim"], m["quote"])
                if v["supports"] and v["confidence"] >= SUPPORT_JUDGE_MIN:
                    support.append({**m, "relation": "supports", "prob": v["confidence"]})
        c["support"] = support
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
        else:
            label, conf = "unverified", min(s, 0.5)

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
                 "evidence_level": e["evidence_level"], "prob": round(e["prob"], 3)}
                for e in sup + con
            ],
        })
    return rows