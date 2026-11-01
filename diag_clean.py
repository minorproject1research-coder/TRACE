import re, sys, unicodedata
from collections import Counter
from apps.api.services import db_service
from apps.api.agents.stage4_factcheck import fact_checker as fc
from apps.api.agents.stage4_factcheck.common import nli_probs


def clean(t: str) -> str:
    t = unicodedata.normalize("NFKC", t)
    t = t.replace("\u2010", "-").replace("\u2011", "-").replace("\u2019", "'")
    t = re.sub(r"[\u00a0\u202f\u2009\u200b]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


q, s = sys.argv[1], sys.argv[2]
claims = fc.load_claims(db_service.get_digests_for_stage4(q, s))

odd = Counter(ch for c in claims for ch in c["claim"] + c["quote"] if ord(ch) > 127)
print("non-ASCII characters:", [(unicodedata.name(ch, "?"), n) for ch, n in odd.most_common(12)])

raw = nli_probs([(c["quote"], c["claim"]) for c in claims])
cln = nli_probs([(clean(c["quote"]), clean(c["claim"])) for c in claims])

n = len(claims)
print(f"\nentailed (>=0.5)  raw: {sum(p['entailment'] >= .5 for p in raw)}/{n}   cleaned: {sum(p['entailment'] >= .5 for p in cln)}/{n}")

print("\nbiggest changes:")
for c, a, b in sorted(zip(claims, raw, cln), key=lambda t: t[2]["entailment"] - t[1]["entailment"], reverse=True)[:6]:
    print(f"raw={a['entailment']:.2f} clean={b['entailment']:.2f} | {c['claim'][:90]}")