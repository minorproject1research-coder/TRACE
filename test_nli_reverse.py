import os, sys
from apps.api.agents.stage4_factcheck import common

# optional: python -m tests.test_nli_reverse <model_name> to compare models
if len(sys.argv) > 1:
    common.NLI_MODEL = sys.argv[1]
    common._nli = None

NEUTRAL_BAD = [
    ("RAG reduces hallucination in LLM outputs.", "RAG adds retrieval latency to every query."),
    ("Hallucination detection methods often rely on token probabilities.", "Detection methods are evaluated on medical text."),
]
TRUE_CONTRA = [
    ("RAG reduced hallucination rates by 42% compared with the baseline.", "RAG increases hallucination rates."),
    ("RAG does not completely eliminate hallucinations, but it reduces their frequency and severity.", "RAG eliminates hallucinations."),
    ("The study found no significant difference in hallucination rates between RAG and the baseline.", "RAG significantly reduced hallucination rates."),
]

def run(name, pairs):
    fwd = common.nli_probs(pairs)
    rev = common.nli_probs([(h, p) for p, h in pairs])   # swapped direction
    print(f"\n{name}")
    for (p, h), f, r in zip(pairs, fwd, rev):
        print(f"  fwd_contra={f['contradiction']:.2f}  rev_contra={r['contradiction']:.2f} | {h}")

print("model:", common.NLI_MODEL)
run("FALSE contradictions (should be low)", NEUTRAL_BAD)
run("TRUE contradictions (should be high)", TRUE_CONTRA)