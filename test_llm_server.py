"""Smoke test for the TRACE model server integration (planner + judge). Needs Tailscale and the x-api-key in .env.

  python test_llm_server.py
"""
import logging
import os
import time

os.environ["USE_LLM_JUDGMENT"] = "true"          # exercise the real judge path in filter_relevant
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

from apps.api.services import trace_llm_service
from apps.api.agents.stage1_planner import question_generator
from apps.api.agents.stage2_retrieval import relevance_filter

print("server:", trace_llm_service.base_url())
print("status:", trace_llm_service.status())

# ---- planner -------------------------------------------------------------------------------------------------
QUESTIONS = [
    "Impact of RAG on hallucination rates in LLMs",
    "How effective is post-training quantization of LLMs to 4-bit?",
    "What are the trade-offs between federated learning and differential privacy for medical imaging?",
]
for q in QUESTIONS:
    t = time.time()
    sub_questions = question_generator.generate(q)
    print(f"\n=== {q}  ({time.time() - t:.1f}s)")
    for sq in sub_questions:
        print(f"  - {sq.main_topic}")
        print(f"      details: {sq.detail_questions}")
        print(f"      queries ({len(sq.queries)}): {sq.queries}")
    empty = [sq.main_topic for sq in sub_questions if not sq.queries]
    print("  sub-questions without queries (will be expanded by query_expansion):", empty or "none")

# ---- judge through the real filter ---------------------------------------------------------------------------
papers = [
    {"title": "Retrieval-Augmented Generation and Hallucination in Large Language Models: A Scholarly Overview",
     "abstract": "Large language models often hallucinate. RAG grounds responses in external documents and reduces hallucination. "
                 "We review the causes, the effectiveness of RAG in reducing hallucinations, and open challenges. " * 2,
     "embedding_similarity": 0.8},
    {"title": "Long paths and cycles in subgraphs of the cube",
     "abstract": "Let Q_n denote the graph of the n-dimensional cube. We show a subgraph with average degree d contains an exponentially long path. " * 2},
    {"title": "RAGTruth: A Hallucination Corpus for Developing Trustworthy Retrieval-Augmented Language Models",
     "abstract": "Retrieval-augmented generation reduces hallucinations in LLMs but they still occur. We present RAGTruth, a word-level "
                 "hallucination corpus of nearly 18,000 responses from several LLMs in RAG settings, and benchmark detection methods. " * 2},
]
t = time.time()
kept = relevance_filter.filter_relevant("How does RAG affect hallucination rates in LLMs?", papers, min_similarity=0.0)
print(f"\n=== filter_relevant with the server judge ({time.time() - t:.1f}s): kept {len(kept)} of {len(papers)}")
for p in papers:
    v = p.get("relevance_verdict")
    print(f"  {'KEPT   ' if p in kept else 'dropped'} {p['title'][:70]} -> {v}")
