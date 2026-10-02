from apps.api.agents.stage2_retrieval.relevance_filter import filter_relevant

sample_papers = [
    {"title": "RAG hallucination reduction study",
     "abstract": "This paper studies how retrieval-augmented generation reduces hallucination rates in LLMs through grounding external knowledge."},
    {"title": "Catalyst discovery with LLMs",
     "abstract": "We use LLMs to discover new catalyst materials for chemical reactions in materials science."},
    {"title": "Evaluating RAG systems",
     "abstract": "A benchmark for evaluating hallucination rates and factual accuracy across RAG pipelines."},
    {"title": "Gamma ray burst detection",
     "abstract": "We present results of processing gamma ray burst propagation through the heliosphere."},
]

results = filter_relevant(
    sub_question="Effect of RAG on hallucination rates",
    papers=sample_papers,
    prefilter_top_k=3,
)

print(f"\n{len(results)} papers shortlisted:\n")
for p in results:
    print(f"  {p['relevance_score']:.3f}  —  {p['title']}")