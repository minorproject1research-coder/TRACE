from apps.api.agents.stage3_summarizer.quote_verifier import verify_quote

chunk = "RAG reduced hallucination rates by 42% compared with the baseline model."

# exact quote -> must pass
assert verify_quote("RAG reduced hallucination rates by 42% compared with the baseline", [chunk])

# PDF-style noise (hyphen + line break, different spacing) -> must still pass
noisy = "RAG reduced halluci-\nnation rates by 42%  compared with the baseline model."
assert verify_quote("RAG reduced hallucination rates by 42% compared with the baseline", [noisy])

# invented claim -> must fail
assert not verify_quote("RAG eliminates hallucination entirely in all settings", [chunk])

# too short -> must fail
assert not verify_quote("RAG works", [chunk])

# empty / None quote -> must fail, not crash
assert not verify_quote("", [chunk])
assert not verify_quote(None, [chunk])

print("ok")