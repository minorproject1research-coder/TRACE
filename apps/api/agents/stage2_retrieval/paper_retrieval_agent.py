"""
Paper Retrieval Agent - Stage 2 of TRACE Research Pipeline

Searches arXiv and Semantic Scholar concurrently for academic papers,
deduplicates results, and returns structured metadata for downstream
Source Reliability Scoring.
"""

import asyncio
import logging
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Output Schema
# ──────────────────────────────────────────────────────────────────────────────

class PaperResult(BaseModel):
    """Structured output for a retrieved paper."""
    title: str
    abstract: str
    authors: list[str]
    year: Optional[int] = None
    venue: Optional[str] = None
    citation_count: Optional[int] = None
    influential_citation_count: Optional[int] = None
    is_preprint: bool = False
    source: str = "arxiv"  # "arxiv" | "semantic_scholar" | "both"
    arxiv_id: Optional[str] = None
    doi: Optional[str] = None
    pdf_url: Optional[str] = None
    published_date: Optional[str] = None
    tldr: Optional[str] = None
    fields_of_study: list[str] = Field(default_factory=list)
    query_variant_matched: list[str] = Field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────────
# Rate Limiter
# ──────────────────────────────────────────────────────────────────────────────

class AsyncRateLimiter:
    """Simple token-bucket rate limiter for async API calls."""

    def __init__(self, calls_per_second: float):
        self._min_interval = 1.0 / calls_per_second
        self._last_call = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_call
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_call = asyncio.get_event_loop().time()


# ──────────────────────────────────────────────────────────────────────────────
# Main Agent Class
# ──────────────────────────────────────────────────────────────────────────────

class PaperRetrievalAgent:
    """
    Retrieves academic papers from arXiv and Semantic Scholar concurrently.

    Usage:
        agent = PaperRetrievalAgent(semantic_scholar_api_key="YOUR_KEY")
        papers = await agent.retrieve(
            sub_question="Impact of RAG on hallucination",
            query_variants=["RAG hallucination reduction", "retrieval augmented generation errors"]
        )
    """

    ARXIV_API_URL = "https://export.arxiv.org/api/query"
    SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1"

    SEMANTIC_SCHOLAR_FIELDS = [
        "title", "abstract", "year", "venue", "citationCount",
        "influentialCitationCount", "authors", "externalIds",
        "tldr", "publicationDate", "fieldsOfStudy", "isOpenAccess",
        "openAccessPdf",
    ]

    def __init__(
        self,
        semantic_scholar_api_key: Optional[str] = None,
        max_results_per_query: int = 10,
    ):
        self.api_key = semantic_scholar_api_key or os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        self.max_results = max_results_per_query

        # Rate limits: arXiv ~0.33 req/s (3s gap), Semantic Scholar ~10 req/s with key
        self._arxiv_limiter = AsyncRateLimiter(calls_per_second=0.33)
        self._s2_limiter = AsyncRateLimiter(calls_per_second=10.0)

    async def retrieve(
        self,
        sub_question: str,
        query_variants: list[str],
    ) -> list[dict]:
        """
        Search all query variants concurrently across both APIs.

        Args:
            sub_question: The research sub-question being investigated.
            query_variants: Paraphrased/reformulated search queries.

        Returns:
            Deduplicated list of paper metadata dicts.
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Fire all (source, query_variant) pairs concurrently
            tasks = []
            for query in query_variants:
                tasks.append(self._safe_arxiv_search(client, query))
                tasks.append(self._safe_s2_search(client, query))

            results = await asyncio.gather(*tasks, return_exceptions=False)

        # Flatten and deduplicate
        all_papers: list[PaperResult] = []
        for paper_list in results:
            all_papers.extend(paper_list)

        merged = self._merge_and_dedupe(all_papers)
        return [p.model_dump() for p in merged]

    # ──────────────────────────────────────────────────────────────────────────
    # arXiv Search
    # ──────────────────────────────────────────────────────────────────────────

    async def _safe_arxiv_search(
        self, client: httpx.AsyncClient, query: str
    ) -> list[PaperResult]:
        """Wrapper that catches errors for a single arXiv query."""
        try:
            return await self._search_arxiv(client, query)
        except Exception as e:
            logger.warning("arXiv search failed for query '%s': %s", query, e)
            return []

    async def _search_arxiv(
        self, client: httpx.AsyncClient, query: str
    ) -> list[PaperResult]:
        """Search arXiv API and parse Atom XML response."""
        await self._arxiv_limiter.acquire()

        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": self.max_results,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }

        # Retry with backoff on transient errors
        for attempt in range(3):
            try:
                resp = await client.get(self.ARXIV_API_URL, params=params)
                resp.raise_for_status()
                break
            except (httpx.HTTPStatusError, httpx.TransportError) as e:
                if attempt == 2:
                    raise
                wait = 2 ** attempt
                logger.debug("arXiv attempt %d failed, retrying in %ds: %s", attempt + 1, wait, e)
                await asyncio.sleep(wait)

        return self._parse_arxiv_xml(resp.text, query)

    def _parse_arxiv_xml(self, xml_text: str, query: str) -> list[PaperResult]:
        """Parse arXiv Atom XML into PaperResult objects."""
        papers = []
        root = ET.fromstring(xml_text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        for entry in root.findall("atom:entry", ns):
            title = self._text(entry, "atom:title", ns).replace("\n", " ").strip()
            abstract = self._text(entry, "atom:summary", ns).replace("\n", " ").strip()
            if not title or not abstract:
                continue

            authors = [
                self._text(a, "atom:name", ns)
                for a in entry.findall("atom:author", ns)
            ]

            arxiv_id = None
            pdf_url = None
            for link in entry.findall("atom:link", ns):
                href = link.get("href", "")
                if link.get("title") == "pdf":
                    pdf_url = href
                elif "/abs/" in href:
                    arxiv_id = href.split("/abs/")[-1]

            published = self._text(entry, "atom:published", ns)
            year = int(published[:4]) if published else None

            papers.append(PaperResult(
                title=title,
                abstract=abstract,
                authors=authors,
                year=year,
                is_preprint=True,  # arXiv papers are preprints
                source="arxiv",
                arxiv_id=arxiv_id,
                pdf_url=pdf_url,
                published_date=published,
                query_variant_matched=[query],
            ))

        return papers

    @staticmethod
    def _text(element: ET.Element, tag: str, ns: dict) -> str:
        """Extract text content from an XML element."""
        child = element.find(tag, ns)
        return child.text.strip() if child is not None and child.text else ""

    # ──────────────────────────────────────────────────────────────────────────
    # Semantic Scholar Search
    # ──────────────────────────────────────────────────────────────────────────

    async def _safe_s2_search(
        self, client: httpx.AsyncClient, query: str
    ) -> list[PaperResult]:
        """Wrapper that catches errors for a single Semantic Scholar query."""
        try:
            return await self._search_semantic_scholar(client, query)
        except Exception as e:
            logger.warning("Semantic Scholar search failed for '%s': %s", query, e)
            return []

    async def _search_semantic_scholar(
        self, client: httpx.AsyncClient, query: str
    ) -> list[PaperResult]:
        """Search Semantic Scholar /paper/search endpoint."""
        await self._s2_limiter.acquire()

        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        params = {
            "query": query,
            "limit": self.max_results,
            "fields": ",".join(self.SEMANTIC_SCHOLAR_FIELDS),
        }

        for attempt in range(3):
            try:
                resp = await client.get(
                    f"{self.SEMANTIC_SCHOLAR_URL}/paper/search",
                    params=params,
                    headers=headers,
                )
                if resp.status_code in (429, 500, 502, 503):
                    wait = 2 ** attempt * 2
                    logger.debug("S2 rate limit/error %d, backing off %ds", resp.status_code, wait)
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                break
            except httpx.TransportError as e:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)
                logger.debug("S2 transport error, retrying: %s", e)
        else:
            return []

        data = resp.json()
        return self._parse_s2_results(data.get("data", []), query)

    def _parse_s2_results(self, papers: list[dict], query: str) -> list[PaperResult]:
        """Convert Semantic Scholar JSON results to PaperResult objects."""
        results = []
        for p in papers:
            ext_ids = p.get("externalIds", {}) or {}
            arxiv_id = ext_ids.get("ArXiv")
            doi = ext_ids.get("DOI")

            authors = [
                a.get("name", "Unknown")
                for a in (p.get("authors") or [])
            ]

            pdf_info = p.get("openAccessPdf") or {}
            pdf_url = pdf_info.get("url")

            tldr_info = p.get("tldr")
            tldr = tldr_info.get("text") if isinstance(tldr_info, dict) else tldr_info

            is_preprint = not p.get("venue")  # No venue usually means preprint

            results.append(PaperResult(
                title=p.get("title", ""),
                abstract=p.get("abstract", "") or "",
                authors=authors,
                year=p.get("year"),
                venue=p.get("venue"),
                citation_count=p.get("citationCount"),
                influential_citation_count=p.get("influentialCitationCount"),
                is_preprint=is_preprint,
                source="semantic_scholar",
                arxiv_id=arxiv_id,
                doi=doi,
                pdf_url=pdf_url,
                published_date=p.get("publicationDate"),
                tldr=tldr,
                fields_of_study=p.get("fieldsOfStudy") or [],
                query_variant_matched=[query],
            ))

        return results

    # ──────────────────────────────────────────────────────────────────────────
    # Deduplication
    # ──────────────────────────────────────────────────────────────────────────

    def _merge_and_dedupe(self, papers: list[PaperResult]) -> list[PaperResult]:
        """
        Deduplicate papers by arXiv ID > DOI > normalized title.

        When duplicates found, merge query_variant_matched lists and
        upgrade source to "both" if paper came from both APIs.
        """
        by_arxiv: dict[str, PaperResult] = {}
        by_doi: dict[str, PaperResult] = {}
        by_title: dict[str, PaperResult] = {}

        for paper in papers:
            key = self._dedupe_key(paper)
            existing = by_arxiv.get(key) or by_doi.get(key) or by_title.get(key)

            if existing is None:
                # First time seeing this paper
                if paper.arxiv_id:
                    by_arxiv[paper.arxiv_id] = paper
                if paper.doi:
                    by_doi[paper.doi] = paper
                by_title[self._norm_title(paper.title)] = paper
            else:
                # Merge: combine query variants and upgrade source
                existing.query_variant_matched.extend(paper.query_variant_matched)
                existing.query_variant_matched = list(set(existing.query_variant_matched))

                if existing.source != paper.source:
                    existing.source = "both"

                # Prefer Semantic Scholar metadata (usually richer)
                if paper.source == "semantic_scholar" and existing.source != "both":
                    if paper.citation_count is not None:
                        existing.citation_count = paper.citation_count
                    if paper.influential_citation_count is not None:
                        existing.influential_citation_count = paper.influential_citation_count
                    if paper.tldr:
                        existing.tldr = paper.tldr
                    if paper.venue:
                        existing.venue = paper.venue
                        existing.is_preprint = False

        # Collect unique papers
        seen_titles: set[str] = set()
        unique: list[PaperResult] = []
        for paper in list(by_arxiv.values()) + list(by_doi.values()):
            norm = self._norm_title(paper.title)
            if norm not in seen_titles:
                seen_titles.add(norm)
                unique.append(paper)

        # Sort by citation count (descending), then year
        unique.sort(
            key=lambda p: (p.citation_count or 0, p.year or 0),
            reverse=True,
        )
        return unique

    def _dedupe_key(self, paper: PaperResult) -> str:
        """Return the best available unique key for deduplication."""
        if paper.arxiv_id:
            return f"arxiv:{paper.arxiv_id}"
        if paper.doi:
            return f"doi:{paper.doi}"
        return f"title:{self._norm_title(paper.title)}"

    @staticmethod
    def _norm_title(title: str) -> str:
        """Normalize title for fuzzy matching: lowercase, strip punctuation."""
        import re
        text = title.lower().strip()
        text = re.sub(r"[^\w\s]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text


# ──────────────────────────────────────────────────────────────────────────────
# Test / Demo
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    async def main():
        agent = PaperRetrievalAgent(max_results_per_query=5)

        sub_question = "How does Retrieval-Augmented Generation affect hallucination rates in LLMs?"
        query_variants = [
            "RAG hallucination reduction LLM",
            "retrieval augmented generation factual accuracy",
        ]

        print(f"Sub-question: {sub_question}")
        print(f"Query variants: {query_variants}\n")

        papers = await agent.retrieve(sub_question, query_variants)

        print(f"Found {len(papers)} unique papers\n")
        for i, paper in enumerate(papers[:5], 1):
            print(f"── Paper {i} ──")
            print(f"  Title:    {paper['title'][:100]}...")
            print(f"  Authors:  {', '.join(paper['authors'][:3])}")
            print(f"  Year:     {paper['year']}")
            print(f"  Venue:    {paper['venue'] or 'N/A'}")
            print(f"  Citations:{paper['citation_count'] or 0}")
            print(f"  Source:   {paper['source']}")
            print(f"  ArXiv ID: {paper['arxiv_id'] or 'N/A'}")
            print(f"  DOI:      {paper['doi'] or 'N/A'}")
            print(f"  TLDR:     {(paper['tldr'] or 'N/A')[:80]}...")
            print()

    asyncio.run(main())
