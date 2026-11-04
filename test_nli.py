from apps.api.agents.stage4_factcheck import common
from apps.api.agents.stage4_factcheck.common import nli_probs

CASES = [
    ("RAG reduced hallucination rates by 42% compared with the baseline.", "RAG lowers hallucination rates.", "entailment"),
    ("RAG reduced hallucination rates by 42% compared with the baseline.", "RAG increases hallucination rates.", "contradiction"),
    ("RAG reduced hallucination rates by 42% compared with the baseline.", "RAG was evaluated on legal documents.", "neutral"),
    ("RAG reduces hallucination in LLM outputs.", "RAG adds retrieval latency to every query.", "neutral"),
    ("RAG does not completely eliminate hallucinations, but it reduces their frequency and severity.", "RAG reduces hallucinations.", "entailment"),
    ("RAG does not completely eliminate hallucinations, but it reduces their frequency and severity.", "RAG eliminates hallucinations.", "contradiction"),
    ("The study found no significant difference in hallucination rates between RAG and the baseline.", "RAG significantly reduced hallucination rates.", "contradiction"),
    ("Retrieved passages do not guarantee that the final answer is grounded.", "Retrieval alone does not ensure grounded answers.", "entailment"),
    ("Hallucination detection methods often rely on token probabilities.", "Detection methods are evaluated on medical text.", "neutral"),
    ("The authors released their code on GitHub.", "The method improves accuracy by 5%.", "neutral"),
]

print("model:", common.NLI_MODEL)
probs = nli_probs([(p, h) for p, h, _ in CASES])
ok = bad_neutral = 0
for (p, h, want), r in zip(CASES, probs):
    got = max(r, key=r.get)
    ok += got == want
    bad_neutral += want == "neutral" and got == "contradiction"
    print("OK  " if got == want else "FAIL", want.ljust(13), "got", got.ljust(13),
          {k: round(v, 2) for k, v in r.items()}, "|", h)
print(f"\n{ok}/{len(CASES)} correct | neutral pairs wrongly called contradiction: {bad_neutral}")

# --- premise-vs-hypothesis similarity: this is what the detector's gate will use ---
from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder
emb = get_embedder()
a = emb.encode([p for p, _, _ in CASES], normalize_embeddings=True)
b = emb.encode([h for _, h, _ in CASES], normalize_embeddings=True)
sims = (a * b).sum(axis=1)

print("\nsimilarity vs NLI contradiction:")
for (p, h, want), s, r in sorted(zip(CASES, sims, probs), key=lambda t: -t[1]):
    print(f"sim={s:.2f}  expected={want.ljust(13)} nli_contra={r['contradiction']:.2f} | {h}")

true_c = [s for (_, _, w), s in zip(CASES, sims) if w == "contradiction"]
bad_n = [s for (_, _, w), s, r in zip(CASES, sims, probs) if w == "neutral" and r["contradiction"] >= 0.7]
if bad_n:
    print(f"\nlowest true-contradiction sim: {min(true_c):.2f} | highest false-contradiction sim: {max(bad_n):.2f}")
    print("gate CAN separate them" if min(true_c) > max(bad_n) else "gate CANNOT separate them")