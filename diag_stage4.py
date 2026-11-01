import sys
from apps.api.services import db_service
from apps.api.agents.stage4_factcheck import fact_checker as fc
from apps.api.agents.stage4_factcheck.common import nli_probs
from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder

q, s = sys.argv[1], sys.argv[2]
claims = fc.load_claims(db_service.get_digests_for_stage4(q, s))
emb = get_embedder().encode([c["claim"] for c in claims], normalize_embeddings=True)

pairs = []
for i in range(len(claims)):
    for j in range(i + 1, len(claims)):
        if claims[i]["doc"] != claims[j]["doc"]:
            pairs.append((float(emb[i] @ emb[j]), i, j))
pairs.sort(reverse=True)

print(f"=== TOP CROSS-DOCUMENT CLAIM PAIRS (CLUSTER_SIM = {fc.CLUSTER_SIM}) ===")
for sim, i, j in pairs[:20]:
    print(f"{sim:.2f}\n  A: {claims[i]['claim']}\n  B: {claims[j]['claim']}")

clusters = fc.build_clusters(claims)
print("\n=== CLUSTERS DROPPED BY verify_support ===")
for c in clusters:
    probs = nli_probs([(m["quote"], c["claim"]) for m in c["members"]])
    best = max(p["entailment"] for p in probs)
    if best < fc.ENTAIL_MIN:
        print(f"best_entail={best:.2f} | claim: {c['claim']}\n   quote: {c['members'][0]['quote']}")