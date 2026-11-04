from apps.api.agents.stage4_factcheck.judge import judge_conflict

JUDGE_MIN = 0.70

# (our claim, their quote, their claim, expected: is it a real conflict?)
CASES = [
    # --- should NOT be conflicts (the two pairs the NLI model got wrong) ---
    ("RAG reduces hallucination in LLM outputs.",
     "RAG adds retrieval latency to every query.",
     "RAG adds retrieval latency to every query.",
     False),
    ("Hallucination detection methods often rely on token probabilities.",
     "Detection methods are evaluated on medical text.",
     "Detection methods are evaluated on medical text.",
     False),

    # --- should be conflicts ---
    ("RAG increases hallucination rates.",
     "RAG reduced hallucination rates by 42% compared with the baseline.",
     "RAG reduces hallucination rates.",
     True),
    ("RAG eliminates hallucinations.",
     "RAG does not completely eliminate hallucinations, but it reduces their frequency and severity.",
     "RAG does not fully eliminate hallucinations.",
     True),
    ("RAG significantly reduced hallucination rates.",
     "The study found no significant difference in hallucination rates between RAG and the baseline.",
     "RAG shows no significant effect on hallucination rates.",
     True),
        ("Draft-model accuracy on language-modeling tasks does not predict speculative decoding performance.",
     "Low-resource languages experience reduced speed-up due to poorer drafter fitness.",
     "Low-resource languages experience reduced speed-up due to poorer drafter fitness.",
     False),
]

ok = 0
for claim, quote, other, want in CASES:
    v = judge_conflict(claim, quote, other)
    got = v["conflicts"] and v["same_aspect"] and v["confidence"] >= JUDGE_MIN
    ok += got == want
    print("OK  " if got == want else "FAIL", "want", str(want).ljust(5), "got", str(got).ljust(5), "|", claim)
    print("     ", v)

print(f"\n{ok}/{len(CASES)} correct")