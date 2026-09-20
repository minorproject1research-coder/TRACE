from apps.api.agents.stage2_retrieval.reliability_scorer import score_paper, score_web_source
from types import SimpleNamespace

# ---------- KNOWN HIGH-QUALITY PAPERS (expect high scores) ----------
high_quality_papers = [
    {
        "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        "venue": "Neural Information Processing Systems",
        "is_preprint": False,
        "citation_count": 3000,
        "influential_citation_count": 200,
        "published_date": "2020-05-22",
    },
    {
        "title": "Ragas: Automated Evaluation of Retrieval Augmented Generation",
        "venue": None,  # was arXiv-only initially
        "is_preprint": True,
        "citation_count": 250,
        "influential_citation_count": 20,
        "published_date": "2023-09-26",
    },
    {
        "title": "MMOA-RAG (NeurIPS paper from your own test run)",
        "venue": "Neural Information Processing Systems",
        "is_preprint": False,
        "citation_count": 45,
        "influential_citation_count": 3,
        "published_date": "2025-01-25",
    },
]

# ---------- KNOWN WEAK/UNVERIFIED PAPERS (expect low-medium scores) ----------
weak_papers = [
    {
        "title": "Random brand-new arXiv preprint, no citations yet",
        "venue": None,
        "is_preprint": True,
        "citation_count": 0,
        "influential_citation_count": 0,
        "published_date": "2026-08-01",
    },
    {
        "title": "Old unrelated physics paper (from your actual noisy results)",
        "venue": None,
        "is_preprint": True,
        "citation_count": None,
        "influential_citation_count": None,
        "published_date": "2020-07-13",
    },
]

# ---------- KNOWN TRUSTED WEB SOURCES (expect high scores) ----------
high_quality_web = [
    SimpleNamespace(url="https://research.google/blog/deeper-insights-into-rag",
                     published_date="2026-01-15", snippet="A" * 300, provider="tavily"),
    SimpleNamespace(url="https://arxiv.org/abs/2005.11401",
                     published_date="2025-11-01", snippet="A" * 250, provider="exa"),
]

# ---------- WEAK/UNKNOWN WEB SOURCES (expect low-medium scores) ----------
weak_web = [
    SimpleNamespace(url="https://randomblog123.com/my-thoughts-on-rag",
                     published_date=None, snippet="short", provider="parallel"),
    SimpleNamespace(url="", published_date=None, snippet="", provider=""),
]

print("=== HIGH-QUALITY PAPERS (expect ~0.7-1.0) ===")
for p in high_quality_papers:
    print(f"  {score_paper(p):.2f}  —  {p['title'][:60]}")

print("\n=== WEAK PAPERS (expect ~0.2-0.4) ===")
for p in weak_papers:
    print(f"  {score_paper(p):.2f}  —  {p['title'][:60]}")

print("\n=== HIGH-QUALITY WEB SOURCES (expect ~0.7-1.0) ===")
for s in high_quality_web:
    print(f"  {score_web_source(s):.2f}  —  {s.url[:60]}")

print("\n=== WEAK WEB SOURCES (expect ~0.1-0.4) ===")
for s in weak_web:
    print(f"  {score_web_source(s):.2f}  —  {s.url[:60] if s.url else '(empty url)'}")