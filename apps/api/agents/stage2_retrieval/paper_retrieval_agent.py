"""
Paper Retrieval Agent - Stage 2 of TRACE Research Pipeline

Searches arXiv and Semantic Scholar concurrently for academic papers,
deduplicates results, and returns structured metadata for downstream
Source Reliability Scoring.
"""

import asyncio
import logging
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional

import httpx
from pydantic import BaseModel, Field

from apps.api.services import db_service

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
    sub_question_id: Optional[str] = None


@dataclass
class Figure:
    label: str
    caption: str
    image_path: Optional[str] = None
    page: Optional[int] = None


@dataclass
class Section:
    heading: str
    text: str
    level: int = 1


@dataclass
class ParsedPaper:
    retrieved_paper_id: str
    title: str
    authors: list[str]
    abstract: str
    sections: list[Section]
    references: list[str]
    figures: list[Figure]
    full_text: str


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
    Retrieves academic papers from arXiv and Semantic Scholar concurrently,
    and parses PDFs for full content extraction using Docling.

    Usage:
        agent = PaperRetrievalAgent(semantic_scholar_api_key="YOUR_KEY")
        
        # Retrieve papers
        papers = await agent.retrieve(
            sub_question="Impact of RAG on hallucination",
            query_variants=["RAG hallucination reduction", "retrieval augmented generation errors"]
        )
        
        # Parse papers in parallel
        parsed = await agent.parse_papers(paper_ids=["id1", "id2", "id3"])
    """

    ARXIV_API_URL = "https://export.arxiv.org/api/query"
    SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1"
    DOCLING_URL = "http://localhost:5001"
    PDFFIGURES_URL = "http://localhost:5002"

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
        pdffigures_url: Optional[str] = None,
        docling_url: Optional[str] = None,
    ):
        self.api_key = semantic_scholar_api_key or os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        self.max_results = max_results_per_query
        self.pdffigures_url = (pdffigures_url or self.PDFFIGURES_URL).rstrip("/")
        self.docling_url = (docling_url or self.DOCLING_URL).rstrip("/")

        # Rate limits: arXiv ~0.33 req/s (3s gap), Semantic Scholar ~10 req/s with key
        self._arxiv_limiter = AsyncRateLimiter(calls_per_second=0.33)
        self._s2_limiter = AsyncRateLimiter(calls_per_second=10.0)

    # ──────────────────────────────────────────────────────────────────────────
    # Paper Parsing (Docling + PDFFigures)
    # ──────────────────────────────────────────────────────────────────────────

    async def parse_papers(
        self,
        paper_ids: list[str],
        max_concurrent: int = 3,
    ) -> list[ParsedPaper]:
        """
        Parse multiple papers in parallel using Docling and PDFFigures.

        Args:
            paper_ids: List of retrieved_paper_id UUIDs to parse.
            max_concurrent: Maximum concurrent parsing operations.

        Returns:
            List of ParsedPaper objects (results also stored in DB).
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _parse_with_semaphore(paper_id: str) -> Optional[ParsedPaper]:
            async with semaphore:
                return await self._parse_single_paper(paper_id)

        tasks = [_parse_with_semaphore(pid) for pid in paper_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        parsed = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("Failed to parse paper %s: %s", paper_ids[i], result)
            elif result is not None:
                parsed.append(result)

        return parsed

    async def _parse_single_paper(self, retrieved_paper_id: str) -> Optional[ParsedPaper]:
        """Parse a single paper by its retrieved_paper_id."""
        paper_metadata = db_service.get_retrieved_paper(retrieved_paper_id)
        if not paper_metadata:
            logger.warning("Paper not found: %s", retrieved_paper_id)
            return None

        pdf_url = self._construct_pdf_url(paper_metadata)
        if not pdf_url:
            logger.warning("No downloadable URL for paper: %s", retrieved_paper_id)
            return None

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                docling_task = self._safe_docling(pdf_url)
                figures_task = self._safe_pdffigures(client, pdf_url)

                docling_result, figures = await asyncio.gather(
                    docling_task, figures_task, return_exceptions=True
                )

                if isinstance(docling_result, Exception):
                    logger.warning("Docling unavailable, using basic metadata: %s", docling_result)
                    docling_result = ParsedPaper(
                        retrieved_paper_id=retrieved_paper_id,
                        title=paper_metadata.get("title", ""),
                        authors=paper_metadata.get("authors", []),
                        abstract=paper_metadata.get("abstract", ""),
                        sections=[],
                        references=[],
                        figures=[],
                        full_text="",
                    )

                docling_result.retrieved_paper_id = retrieved_paper_id
                docling_result.figures = figures if isinstance(figures, list) else []

                self._store_parsed_paper(docling_result)
                return docling_result

        except Exception as e:
            logger.error("Paper parsing failed for %s: %s", retrieved_paper_id, e)
            return None

    async def _safe_docling(self, pdf_url: str):
        try:
            return await self._parse_with_docling(pdf_url)
        except Exception as e:
            return e

    async def _safe_pdffigures(self, client: httpx.AsyncClient, pdf_bytes: bytes):
        try:
            return await self._parse_with_pdffigures(client, pdf_bytes)
        except Exception as e:
            return []

    def _construct_pdf_url(self, paper: dict) -> Optional[str]:
        """Construct PDF download URL from paper metadata."""
        arxiv_id = paper.get("arxiv_id")
        if arxiv_id:
            return f"https://arxiv.org/pdf/{arxiv_id}"

        pdf_url = paper.get("pdf_url")
        if pdf_url:
            return pdf_url

        doi = paper.get("doi")
        if doi:
            return f"https://doi.org/{doi}"

        return None

    def _store_parsed_paper(self, paper: ParsedPaper) -> None:
        """Store parsed paper content in the database."""
        db_service.write_parsed_paper(
            retrieved_paper_id=paper.retrieved_paper_id,
            title=paper.title,
            authors=paper.authors,
            abstract=paper.abstract,
            sections=[{"heading": s.heading, "text": s.text, "level": s.level} for s in paper.sections],
            references=paper.references,
            figures=[{"label": f.label, "caption": f.caption, "image_path": f.image_path, "page": f.page} for f in paper.figures],
            full_text=paper.full_text,
        )

    async def _download_pdf(self, client: httpx.AsyncClient, url: str) -> bytes:
        """Download PDF from URL."""
        logger.info("Downloading PDF from: %s", url[:100])
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
        logger.info("Downloaded PDF: %d bytes", len(resp.content))
        return resp.content

    async def _parse_with_docling(self, pdf_url: str) -> ParsedPaper:
        """Parse PDF using Docling Docker API for metadata, sections, and references."""
        logger.info("Parsing PDF with Docling Docker API: %s", pdf_url[:100])
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.docling_url}/v1/convert/source",
                json={
                    "sources": [{"kind": "http", "url": pdf_url}],
                    "output_formats": ["markdown"],
                },
            )
            resp.raise_for_status()
            data = resp.json()
        
        title = "Unknown"
        authors = []
        abstract = ""
        sections = []
        references = []
        
        document = data.get("document", {})
        md_content = ""
        
        if document and "md_content" in document:
            md_content = document["md_content"] or ""
        elif "md_content" in data:
            md_content = data["md_content"] or ""
        
        lines = md_content.split("\n")
        current_section = None
        in_abstract = False
        in_references = False
        authors_raw = []
        
        for line in lines:
            line_stripped = line.strip()
            
            if line_stripped.startswith("# ") and title == "Unknown":
                title = line_stripped[2:].strip()
            elif line_stripped.startswith("## ") and title == "Unknown":
                title = line_stripped[3:].strip()
            elif line_stripped.lower().startswith("## abstract"):
                in_abstract = True
                in_references = False
                current_section = None
            elif line_stripped.lower().startswith("## ") and in_abstract:
                in_abstract = False
                heading = line_stripped.lstrip("#").strip()
                if "reference" in heading.lower():
                    in_references = True
                    current_section = None
                else:
                    current_section = Section(heading=heading, text="", level=1)
                    sections.append(current_section)
            elif line_stripped.startswith("## ") or line_stripped.startswith("### "):
                in_abstract = False
                heading = line_stripped.lstrip("#").strip()
                if "reference" in heading.lower():
                    in_references = True
                    current_section = None
                else:
                    current_section = Section(heading=heading, text="", level=1)
                    sections.append(current_section)
            elif in_abstract and line_stripped:
                abstract += line_stripped + " "
            elif in_references and line_stripped:
                if line_stripped.startswith("- [") or line_stripped.startswith("["):
                    references.append(line_stripped)
            elif current_section and line_stripped:
                current_section.text += line_stripped + "\n"
            
            if not authors_raw and title != "Unknown" and line_stripped and not line_stripped.startswith("#"):
                if re.match(r'^[\d\s,\s*]+$', line_stripped):
                    continue
                if any(c in line_stripped.lower() for c in ["university", "lab", "institute", "dept", "center", "school"]):
                    continue
                if line_stripped.startswith("http") or line_stripped.startswith("<!--"):
                    continue
                if len(line_stripped) > 5:
                    authors_raw.append(line_stripped)
        
        if not title or title == "Unknown":
            title = document.get("title", "Unknown") or data.get("title", "Unknown") or "Unknown"
        
        parsed_authors = []
        if authors_raw:
            raw = authors_raw[0]
            for name in raw.split(","):
                name = name.strip()
                name = name.lstrip("∗*").strip()
                if name and len(name) > 2 and not name.isdigit():
                    parsed_authors.append(name)
        
        abstract = abstract.strip()
        
        return ParsedPaper(
            retrieved_paper_id="",
            title=title,
            authors=parsed_authors,
            abstract=abstract,
            sections=sections,
            references=references,
            figures=[],
            full_text=md_content,
        )

    async def _parse_with_pdffigures(self, client: httpx.AsyncClient, pdf_url: str) -> list[Figure]:
        """Parse PDF using PDFFigures 2.0 for figure/table extraction."""
        logger.info("Sending PDF to PDFFigures 2.0 for figure extraction")
        try:
            pdf_resp = await client.get(pdf_url, follow_redirects=True)
            pdf_resp.raise_for_status()
            
            resp = await client.post(
                f"{self.pdffigures_url}/extract",
                files={"file": ("paper.pdf", pdf_resp.content, "application/pdf")},
            )
            resp.raise_for_status()
            return self._parse_pdffigures_response(resp.json())
        except Exception as e:
            logger.warning("PDFFigures parsing failed: %s", e)
            return []

    async def _safe_pdffigures(self, client: httpx.AsyncClient, pdf_url: str):
        try:
            return await self._parse_with_pdffigures(client, pdf_url)
        except Exception as e:
            return e

    def _parse_pdffigures_response(self, data: dict) -> list[Figure]:
        """Parse PDFFigures 2.0 JSON response into Figure objects."""
        figures = []
        inner = data.get("data", data)
        for item in inner.get("figures", []):
            figures.append(Figure(
                label=item.get("name", "") or item.get("label", ""),
                caption=item.get("caption", ""),
                image_path=item.get("renderURL") or item.get("imagePath"),
                page=item.get("page"),
            ))
        return figures

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
