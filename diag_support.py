import sys
from apps.api.services import db_service
from apps.api.services.llm_service import squeezer_json
from apps.api.agents.stage4_factcheck import fact_checker as fc
from apps.api.agents.stage4_factcheck.common import nli_probs

PROMPT = """Quote from a research source: "{quote}"
Claim: "{claim}"

Read the quote as written. Does it support the claim (the claim follows from the quote,
possibly in different words)? Ignore formatting noise in the quote.
Return ONLY JSON: {{"supports": true, "reason": "one sentence"}}
(use true or false for supports)"""

q, s = sys.argv[1], sys.argv[2]
claims = fc.load_claims(db_service.get_digests_for_stage4(q, s))
clusters = fc.build_clusters(claims)

dropped = []
for c in clusters:
    probs = nli_probs([(m["quote"], c["claim"]) for m in c["members"]])
    k = max(range(len(probs)), key=lambda i: probs[i]["entailment"])
    if probs[k]["entailment"] < fc.ENTAIL_MIN:
        dropped.append((c["claim"], c["members"][k]["quote"], probs[k]))

print(f"dropped by NLI: {len(dropped)} of {len(clusters)}\n")
agree = 0
for claim, quote, p in dropped:
    try:
        v = squeezer_json(PROMPT.format(quote=quote, claim=claim))
        sup = bool(v.get("supports"))
    except Exception as e:
        sup, v = False, {"reason": f"judge failed: {e}"}
    agree += sup
    print(f"NLI ent={p['entailment']:.2f} neu={p['neutral']:.2f} con={p['contradiction']:.2f} | judge supports={sup}")
    print(f"  claim: {claim}\n  quote: {quote}\n  judge: {v.get('reason')}\n")

print(f"judge says the quote supports the claim in {agree} of {len(dropped)} NLI-dropped clusters")