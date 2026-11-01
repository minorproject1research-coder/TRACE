import sys
from apps.api.services import db_service
from apps.api.services.llm_service import squeezer_json
from apps.api.agents.stage4_factcheck import fact_checker as fc
from apps.api.agents.stage4_factcheck.judge import SAME_PROMPT
from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder

q, s = sys.argv[1], sys.argv[2]
claims = fc.load_claims(db_service.get_digests_for_stage4(q, s))
emb = get_embedder().encode([c["claim"] for c in claims], normalize_embeddings=True)

pairs = sorted(
    ((float(emb[i] @ emb[j]), i, j)
     for i in range(len(claims)) for j in range(i + 1, len(claims))
     if claims[i]["doc"] != claims[j]["doc"]),
    reverse=True,
)[:15]

for sim, i, j in pairs:
    v = squeezer_json(SAME_PROMPT.format(a=claims[i]["claim"], b=claims[j]["claim"]))
    print(f"sim={sim:.2f} same={v.get('same')}\n  A: {claims[i]['claim']}\n  B: {claims[j]['claim']}\n  why: {v.get('reason')}\n")