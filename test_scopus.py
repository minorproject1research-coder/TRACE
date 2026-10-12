"""Live check of the Scopus path through the host, run from the dev machine AFTER the router is deployed on the host.

    python test_scopus.py                       # default query
    python test_scopus.py "RAG hallucination"   # your own query

Prints the host status, the Scopus query that is built, and the papers the pipeline would receive.
"""
import asyncio
import logging
import sys

import httpx

from apps.api.agents.stage2_retrieval.paper_retrieval_agent import PaperRetrievalAgent
from apps.api.services import trace_llm_service

logging.basicConfig(level=logging.INFO, format="%(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

text = " ".join(sys.argv[1:]) or "speculative decoding inference latency"

try:
    r = httpx.get(f"{trace_llm_service.base_url()}/scopus/status", headers={"x-api-key": trace_llm_service._api_key()}, timeout=60)
    print("host /scopus/status ->", r.status_code, r.text[:300])
except Exception as e:
    print("host /scopus/status failed:", type(e).__name__, e)

agent = PaperRetrievalAgent(max_results_per_query=5)
print("\nScopus query:", agent._scopus_query(text))
papers = asyncio.run(agent._safe_scopus_search(text))
print(f"\n{len(papers)} papers" + ("" if papers else "  (see the warning above if Scopus was skipped)"))
for p in papers[:10]:
    print(f"- {p.title[:75]} | {p.venue} | {p.year} | cited {p.citation_count} | doi {p.doi} | abstract {len(p.abstract)} chars | {len(p.authors)} authors")
