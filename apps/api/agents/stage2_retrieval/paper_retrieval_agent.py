"""
Paper Retrieval Agent - Stage 2 of TRACE Research Pipeline

Searches arXiv and Semantic Scholar concurrently for academic papers,
deduplicates results, and returns structured metadata for downstream
Source Reliability Scoring.
"""

import asyncio
import logging
import os
import random
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional

import httpx
from pydantic import BaseModel, Field

from apps.api.agents.stage2_retrieval.key_pool import KeyPool
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
    source: str = "arxiv"  # "arxiv" | "semantic_scholar" | "ieee" | "openalex" | "both"
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

    def penalize(self, seconds: float):
        """Push the next allowed call at least `seconds` into the future, so every
        concurrent caller backs off after one of them is rate limited."""
        earliest = asyncio.get_event_loop().time() + seconds - self._min_interval
        self._last_call = max(self._last_call, earliest)


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
    IEEE_API_URL = "https://ieeexploreapi.ieee.org/api/v1/search/articles"
    OPENALEX_API_URL = "https://api.openalex.org/works"
    # Only real research outputs, in English, with an abstract (drops peer-review records, paratext, datasets...)
    OPENALEX_BASE_FILTER = "type:article|preprint,language:en,has_abstract:true"
    OPENALEX_STOPWORDS = frozenset(
        "a an the of in on for to and or how do does what which why is are be by with from as at into "
        "using use via that this these those can it its their than then between across over under about "
        "whether when where who whom while within without".split()
    )
    OPENALEX_SELECT = ",".join([
        "id", "doi", "title", "publication_year", "publication_date", "cited_by_count",
        "abstract_inverted_index", "authorships", "primary_location", "best_oa_location",
        "open_access", "type", "topics",
    ])
    UNPAYWALL_API_URL = "https://api.unpaywall.org/v2"
    UNPAYWALL_EMAIL = "minorproject1research@gmail.com"

    SEMANTIC_SCHOLAR_FIELDS = [
        "title", "abstract", "year", "venue", "citationCount",
        "influentialCitationCount", "authors", "externalIds",
        "tldr", "publicationDate", "fieldsOfStudy", "isOpenAccess",
        "openAccessPdf",
    ]

    def __init__(
        self,
        semantic_scholar_api_key: Optional[str] = None,
        ieee_api_key: Optional[str] = None,
        openalex_api_key: Optional[str] = None,
        max_results_per_query: int = 10,
        min_citations: int = 0,
        pdffigures_url: Optional[str] = None,
        docling_url: Optional[str] = None,
    ):
        self.api_key = semantic_scholar_api_key or os.getenv("SEMANTIC_SCHOLAR_API_KEY")
        self.ieee_key = ieee_api_key or os.getenv("IEEE_API_KEY")
        # OpenAlex is optional: without any key it is skipped entirely. Several keys
        # (OPENALEX_API_KEYS, comma-separated; OPENALEX_API_KEY also accepted) form a rotation pool.
        raw_keys = openalex_api_key if openalex_api_key is not None else (
            f"{os.getenv('OPENALEX_API_KEYS', '')},{os.getenv('OPENALEX_API_KEY', '')}"
        )
        openalex_keys = list(dict.fromkeys(k.strip() for k in raw_keys.split(",") if k.strip()))
        self._openalex_pool: Optional[KeyPool] = KeyPool(openalex_keys) if openalex_keys else None
        self.openalex_max_attempts = max(1, int(os.getenv("OPENALEX_MAX_ATTEMPTS", "4")))
        self.openalex_backoff_base = float(os.getenv("OPENALEX_BACKOFF_BASE_SECONDS", "2"))
        self.openalex_backoff_cap = float(os.getenv("OPENALEX_BACKOFF_CAP_SECONDS", "30"))
        self.openalex_timeout = float(os.getenv("OPENALEX_TIMEOUT_SECONDS", "90"))  # reranked searches are slow
        # Search modes (each is one API call per query variant): AI-reranked keyword search (~20 credits)
        # and semantic search (~10 credits). They surface different papers, so both are on by default.
        self.openalex_rerank = os.getenv("OPENALEX_RERANK", "true").lower() not in ("0", "false", "no")
        self.openalex_semantic = os.getenv("OPENALEX_SEMANTIC", "true").lower() not in ("0", "false", "no")
        self._openalex_warned = False  # log "no usable OpenAlex keys" only once
        self.max_results = max_results_per_query
        self.min_citations = min_citations
        self.pdffigures_url = (pdffigures_url or os.getenv("PDFFIGURES_URL", "http://localhost:5002")).rstrip("/")
        self.docling_url = (docling_url or os.getenv("DOCLING_URL", "http://localhost:5001")).rstrip("/")

        # Semantic Scholar search retry policy (env-configurable). With the defaults the
        # waits are 5, 10, 20, 40, 60s (+ up to 25% jitter) across 6 attempts.
        self.s2_max_attempts = max(1, int(os.getenv("S2_MAX_ATTEMPTS", "6")))
        self.s2_backoff_base = float(os.getenv("S2_BACKOFF_BASE_SECONDS", "5"))
        self.s2_backoff_cap = float(os.getenv("S2_BACKOFF_CAP_SECONDS", "60"))

        self._arxiv_limiter = AsyncRateLimiter(calls_per_second=0.33)
        self._s2_limiter = AsyncRateLimiter(calls_per_second=0.1 if not self.api_key else 10.0)
        self._ieee_limiter = AsyncRateLimiter(calls_per_second=0.5)
        self._openalex_limiter = AsyncRateLimiter(calls_per_second=5.0)  # API allows 100/s

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

        pdf_urls = self._construct_pdf_url(paper_metadata)
        if not pdf_urls:
            logger.warning("No downloadable URL for paper: %s", retrieved_paper_id)
            return None

        from urllib.parse import urlparse
        failed_hosts: set[str] = set()
        last_error = None

        for pdf_url in pdf_urls:
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    pdf_bytes = await self._download_pdf(client, pdf_url)

                    docling_task = self._safe_docling(pdf_bytes)
                    figures_task = self._safe_pdffigures(client, pdf_bytes)

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
                last_error = e
                failed_hosts.add(urlparse(pdf_url).netloc)
                logger.warning("Failed to download from %s: %s: %r", pdf_url[:80], type(e).__name__, e)
                continue

        doi = paper_metadata.get("doi")
        if doi:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    unpaywall_url = await self._get_unpaywall_url(client, doi, failed_hosts)
                    if unpaywall_url:
                        pdf_bytes = await self._download_pdf(client, unpaywall_url)

                        docling_task = self._safe_docling(pdf_bytes)
                        figures_task = self._safe_pdffigures(client, pdf_bytes)

                        docling_result, figures = await asyncio.gather(
                            docling_task, figures_task, return_exceptions=True
                        )

                        if isinstance(docling_result, Exception):
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
                logger.warning("Unpaywall fallback failed for %s: %s: %r", doi, type(e).__name__, e)

        pdf_url = pdf_urls[0] if pdf_urls else None
        if pdf_url:
            try:
                pdf_bytes = await self._download_pdf_playwright(pdf_url)
                if pdf_bytes:
                    async with httpx.AsyncClient(timeout=60.0) as client:
                        docling_task = self._safe_docling(pdf_bytes)
                        figures_task = self._safe_pdffigures(client, pdf_bytes)

                        docling_result, figures = await asyncio.gather(
                            docling_task, figures_task, return_exceptions=True
                        )

                        if isinstance(docling_result, Exception):
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
                logger.warning("Playwright fallback failed: %s: %r", type(e).__name__, e)

        logger.error("All PDF URLs failed for %s: %s: %r", retrieved_paper_id, type(last_error).__name__ if last_error else "None", last_error)
        return ParsedPaper(
            retrieved_paper_id=retrieved_paper_id,
            title="PDF access denied - unable to download",
            authors=[],
            abstract="",
            sections=[],
            references=[],
            figures=[],
            full_text="",
        )

    async def _safe_docling(self, pdf_bytes: bytes):
        try:
            return await self._parse_with_docling(pdf_bytes)
        except Exception as e:
            return e

    async def _safe_pdffigures(self, client: httpx.AsyncClient, pdf_bytes: bytes):
        try:
            return await self._parse_with_pdffigures(client, pdf_bytes)
        except Exception as e:
            return []

    async def _download_pdf_playwright(self, url: str) -> bytes:
        """Download PDF using undetected Playwright with click-through flow."""
        from undetected_playwright.async_api import async_playwright
        from urllib.parse import urlparse

        logger.info("Trying undetected Playwright download for: %s", url[:80])

        parsed = urlparse(url)
        is_mdpi = "mdpi.com" in parsed.netloc

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    accept_downloads=True,
                )
                page = await context.new_page()

                if is_mdpi:
                    body = await self._playwright_mdpi_flow(page, url)
                else:
                    body = await self._playwright_direct_flow(page, url)

                if body:
                    return body
                raise ValueError("Playwright: failed to download PDF")
            finally:
                await browser.close()

    async def _playwright_mdpi_flow(self, page, pdf_url: str) -> Optional[bytes]:
        """MDPI-specific: navigate to landing page, extract fresh PDF URL, download via click or navigation."""
        from urllib.parse import urljoin

        landing_url = pdf_url.split("/pdf")[0]
        logger.info("MDPI flow: navigating to landing page: %s", landing_url[:80])

        response = await page.goto(landing_url, wait_until="networkidle", timeout=30000)
        if not response or response.status != 200:
            logger.warning("MDPI landing page returned status %s", response.status if response else "None")
            return None

        fresh_pdf_url = await page.get_attribute('meta[name="citation_pdf_url"]', "content")
        if not fresh_pdf_url:
            logger.warning("MDPI: could not extract citation_pdf_url from landing page")
            return None

        if not fresh_pdf_url.startswith("http"):
            fresh_pdf_url = urljoin(landing_url, fresh_pdf_url)

        logger.info("MDPI: fresh PDF URL: %s", fresh_pdf_url[:80])

        body = None

        try:
            async with page.expect_download(timeout=10000) as download_info:
                await page.click('a:has-text("Download PDF")')
            download = await download_info.value
            path = await download.path()
            with open(path, "rb") as f:
                body = f.read()
            logger.info("MDPI: PDF captured via click-triggered download (%d bytes)", len(body))
        except Exception as e:
            logger.info("MDPI: click download did not fire (%s), trying direct navigation", type(e).__name__)

        if body is None:
            try:
                async with page.expect_download(timeout=10000) as download_info:
                    try:
                        await page.goto(fresh_pdf_url, wait_until="commit", timeout=10000)
                    except Exception:
                        pass
                download = await download_info.value
                path = await download.path()
                with open(path, "rb") as f:
                    body = f.read()
                logger.info("MDPI: PDF captured via direct-navigation download (%d bytes)", len(body))
            except Exception as e:
                logger.warning("MDPI: direct-navigation download also failed: %s: %r", type(e).__name__, e)

        if body is None or not body.startswith(b"%PDF"):
            logger.warning("MDPI: no valid PDF captured from either attempt")
            return None

        return body

    async def _playwright_direct_flow(self, page, url: str) -> Optional[bytes]:
        """Direct download for non-MDPI URLs."""
        response = await page.goto(url, wait_until="networkidle", timeout=30000)

        if not response or response.status != 200:
            return None

        content_type = response.headers.get("content-type", "").lower()
        if "pdf" in content_type:
            body = await response.body()
            if body and body.startswith(b"%PDF"):
                logger.info("Playwright downloaded %d bytes (real PDF)", len(body))
                return body

        content = await page.content()
        if "Access Denied" in content or len(content) < 2000:
            return None

        return None

    def _construct_pdf_url(self, paper: dict) -> list[str]:
        """Construct PDF download URLs from paper metadata (ordered by reliability)."""
        urls = []

        arxiv_id = paper.get("arxiv_id")
        if arxiv_id:
            urls.append(f"https://arxiv.org/pdf/{arxiv_id}")

        pdf_url = paper.get("pdf_url")
        if pdf_url:
            urls.append(pdf_url)

        doi = paper.get("doi")
        if doi:
            urls.append(f"https://doi.org/{doi}")

        return urls

    async def _get_unpaywall_url(self, client: httpx.AsyncClient, doi: str, failed_hosts: set[str] = None) -> Optional[str]:
        """Query Unpaywall API for open access PDF URL. Skips already-failed hosts."""
        if not doi:
            return None
        if failed_hosts is None:
            failed_hosts = set()
        try:
            resp = await client.get(
                f"{self.UNPAYWALL_API_URL}/{doi}",
                params={"email": self.UNPAYWALL_EMAIL},
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                candidates = []
                best = data.get("best_oa_location")
                if best:
                    candidates.append(best)
                candidates.extend(data.get("oa_locations") or [])

                for loc in candidates:
                    if not loc:
                        continue
                    pdf_url = loc.get("url_for_pdf") or loc.get("url")
                    if not pdf_url:
                        continue
                    from urllib.parse import urlparse
                    host = urlparse(pdf_url).netloc
                    if any(failed in host for failed in failed_hosts):
                        logger.debug("Skipping Unpaywall URL (failed host): %s", pdf_url[:80])
                        continue

                    if "doaj.org" in host:
                        pdf_url = await self._parse_doaj_for_pdf(client, pdf_url)
                        if not pdf_url:
                            continue

                    logger.info("Unpaywall found OA URL for %s: %s", doi, pdf_url[:80])
                    return pdf_url
        except Exception as e:
            logger.debug("Unpaywall lookup failed for %s: %s", doi, e)
        return None

    async def _parse_doaj_for_pdf(self, client: httpx.AsyncClient, doaj_url: str) -> Optional[str]:
        """Parse DOAJ landing page to find actual PDF link."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        try:
            resp = await client.get(doaj_url, follow_redirects=True, headers=headers, timeout=15.0)
            if resp.status_code != 200:
                return None
            content = resp.text
            import re
            pdf_links = re.findall(r'href=["\']([^"\']*\.pdf[^"\']*)["\']', content, re.IGNORECASE)
            if pdf_links:
                pdf_url = pdf_links[0]
                if not pdf_url.startswith("http"):
                    from urllib.parse import urljoin
                    pdf_url = urljoin(doaj_url, pdf_url)
                logger.info("DOAJ landing page has PDF link: %s", pdf_url[:80])
                return pdf_url
        except Exception as e:
            logger.debug("DOAJ parsing failed: %s", e)
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
        """Download PDF from URL with browser-like headers. Tries fallback strategies."""
        logger.info("Downloading PDF from: %s", url[:100])
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.mdpi.com/",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        resp = await client.get(url, follow_redirects=True, headers=headers)
        if resp.status_code == 403 and "?" in url:
            clean_url = url.split("?")[0]
            logger.info("Retrying without query params: %s", clean_url)
            resp = await client.get(clean_url, follow_redirects=True, headers=headers)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "").lower()
        if "pdf" not in content_type:
            raise ValueError(f"Non-PDF response (content-type: {content_type}) for {url[:80]}")

        logger.info("Downloaded PDF: %d bytes", len(resp.content))
        return resp.content

    async def _parse_with_docling(self, pdf_bytes: bytes) -> ParsedPaper:
        """Parse PDF using Docling Docker API for metadata, sections, and references."""
        import base64
        
        b64_data = base64.b64encode(pdf_bytes).decode("utf-8")
        logger.info("Parsing PDF with Docling Docker API (%d bytes)", len(pdf_bytes))
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.docling_url}/v1/convert/source",
                json={
                    "sources": [{"kind": "file", "base64_string": b64_data, "filename": "paper.pdf"}],
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
        
        if not md_content or len(md_content.strip()) < 50:
            raise ValueError("Docling returned empty or minimal content")
        
        lines = md_content.split("\n")
        current_section = None
        in_abstract = False
        in_references = False
        authors_raw = []
        collect_authors = False
        stop_authors = False
        
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
                collect_authors = False
                stop_authors = True
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
                elif re.match(r'^\d+\.\s', line_stripped):
                    references.append(line_stripped)
            elif current_section and line_stripped:
                current_section.text += line_stripped + "\n"
            
            if not stop_authors and not authors_raw and title != "Unknown" and line_stripped and not line_stripped.startswith("#"):
                if re.match(r'^[\d\s,\s*]+$', line_stripped):
                    continue
                if any(c in line_stripped.lower() for c in ["university", "lab", "institute", "dept", "center", "school"]):
                    continue
                if line_stripped.startswith("http") or line_stripped.startswith("<!--"):
                    continue
                if len(line_stripped) > 5:
                    collect_authors = True
                    authors_raw.append(line_stripped)
            elif collect_authors and not stop_authors and line_stripped and not line_stripped.startswith("#"):
                if re.match(r'^[\d\s,\s*]+$', line_stripped):
                    collect_authors = False
                elif any(c in line_stripped.lower() for c in ["university", "lab", "institute", "dept", "center", "school"]):
                    collect_authors = False
                elif line_stripped.startswith("http") or line_stripped.startswith("<!--"):
                    collect_authors = False
                elif len(line_stripped) > 5:
                    authors_raw.append(line_stripped)
        
        if not title or title == "Unknown":
            title = document.get("title", "Unknown") or data.get("title", "Unknown") or "Unknown"
        
        parsed_authors = []
        for raw_line in authors_raw:
            for name in raw_line.split(","):
                name = name.strip()
                name = re.sub(r'\s*\d+\s*$', '', name).strip()
                name = re.sub(r'^[\d\s*]+', '', name).strip()
                name = name.lstrip("∗*").strip()
                if name and len(name) > 2 and not name.isdigit():
                    parsed_authors.append(name)
        parsed_authors = list(dict.fromkeys(parsed_authors))
        
        abstract = abstract.strip()
        
        if not abstract:
            for line in lines:
                line_stripped = line.strip()
                if re.match(r'^abstract[\s.:]', line_stripped, re.IGNORECASE):
                    abstract = re.sub(r'^abstract[\s.:]*', '', line_stripped, flags=re.IGNORECASE).strip()
                    if abstract:
                        break
        
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

    async def _parse_with_pdffigures(self, client: httpx.AsyncClient, pdf_bytes: bytes) -> list[Figure]:
        """Parse PDF using PDFFigures 2.0 for figure/table extraction."""
        logger.info("Sending PDF to PDFFigures 2.0 for figure extraction (%d bytes)", len(pdf_bytes))
        try:
            resp = await client.post(
                f"{self.pdffigures_url}/extract",
                files={"file": ("paper.pdf", pdf_bytes, "application/pdf")},
            )
            resp.raise_for_status()
            return self._parse_pdffigures_response(resp.json())
        except Exception as e:
            logger.warning("PDFFigures parsing failed: %s", e)
            return []

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
            tasks = []
            for query in query_variants:
                tasks.append(self._safe_arxiv_search(client, query))
                tasks.append(self._safe_s2_search(client, query))
                tasks.append(self._safe_s2_search(client, f"{query} IEEE"))
                tasks.append(self._safe_ieee_search(client, query))
                if self._openalex_pool:  # no key -> OpenAlex is skipped
                    tasks.append(self._safe_openalex_search(client, query))

            results = await asyncio.gather(*tasks, return_exceptions=False)

        # Flatten and deduplicate
        all_papers: list[PaperResult] = []
        for paper_list in results:
            all_papers.extend(paper_list)

        merged = self._merge_and_dedupe(all_papers)

        async with httpx.AsyncClient(timeout=30.0) as client:
            await self._enrich_citation_counts(client, merged)

        if self.min_citations > 0:
            merged = [p for p in merged if (p.citation_count or 0) >= self.min_citations]

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
        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        params = {
            "query": query,
            "limit": self.max_results,
            "fields": ",".join(self.SEMANTIC_SCHOLAR_FIELDS),
        }
        if self.min_citations > 0:
            params["minCitationCount"] = self.min_citations

        max_attempts = self.s2_max_attempts
        for attempt in range(max_attempts):
            # Every attempt (not just the first) goes through the shared limiter.
            await self._s2_limiter.acquire()
            try:
                resp = await client.get(
                    f"{self.SEMANTIC_SCHOLAR_URL}/paper/search",
                    params=params,
                    headers=headers,
                )
                if resp.status_code in (429, 500, 502, 503):
                    # Exponential backoff with jitter; honour Retry-After when S2 sends it.
                    wait = min(self.s2_backoff_cap, self.s2_backoff_base * 2 ** attempt)
                    wait += random.uniform(0, wait * 0.25)
                    retry_after = resp.headers.get("Retry-After", "")
                    if retry_after.isdigit():
                        wait = max(wait, float(retry_after))
                    if attempt == max_attempts - 1:
                        break
                    logger.warning("S2 %d for '%s' (attempt %d/%d), backing off %.1fs",
                                   resp.status_code, query[:60], attempt + 1, max_attempts, wait)
                    self._s2_limiter.penalize(wait)  # pause all concurrent S2 callers too
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                break
            except httpx.TransportError as e:
                if attempt == max_attempts - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
                logger.debug("S2 transport error, retrying: %s", e)
        else:
            return []

        if resp.status_code in (429, 500, 502, 503):
            logger.warning("S2 gave up on '%s' after %d attempts (last status %d)",
                           query[:60], max_attempts, resp.status_code)
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
    # IEEE Xplore Search
    # ──────────────────────────────────────────────────────────────────────────

    async def _safe_ieee_search(
        self, client: httpx.AsyncClient, query: str
    ) -> list[PaperResult]:
        try:
            return await self._search_ieee(client, query)
        except httpx.HTTPStatusError as e:
            # Don't log str(e): it contains the request URL, which carries the apikey.
            logger.warning("IEEE search failed for '%s': HTTP %d", query, e.response.status_code)
            return []
        except Exception as e:
            logger.warning("IEEE search failed for '%s': %s", query, type(e).__name__)
            return []

    async def _search_ieee(
        self, client: httpx.AsyncClient, query: str
    ) -> list[PaperResult]:
        if not self.ieee_key:
            return []

        await self._ieee_limiter.acquire()

        params = {
            "querytext": query,
            "max_records": self.max_results,
            "apikey": self.ieee_key,
            "sort_field": "article_number",
            "sort_order": "desc",
        }

        for attempt in range(3):
            try:
                resp = await client.get(self.IEEE_API_URL, params=params)
                if resp.status_code == 429:
                    wait = 2 ** attempt * 5
                    logger.warning("IEEE rate limited, backing off %ds", wait)
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                data = resp.json()
                return self._parse_ieee_results(data, query)
            except httpx.TransportError as e:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)

        return []

    def _parse_ieee_results(self, data: dict, query: str) -> list[PaperResult]:
        articles = data.get("articles", [])
        papers = []

        for article in articles:
            authors_data = article.get("authors", {}).get("authors", [])
            authors = [a.get("full_name", "") for a in authors_data if a.get("full_name")]

            pdf_url = article.get("pdf_url") or article.get("html_url")
            doi = article.get("doi")

            papers.append(PaperResult(
                title=article.get("title", ""),
                abstract=article.get("abstract", "") or "",
                authors=authors,
                year=article.get("publication_year"),
                venue=article.get("publication_title", ""),
                citation_count=article.get("citing_paper_count"),
                influential_citation_count=None,
                is_preprint=False,
                source="ieee",
                arxiv_id=None,
                doi=doi,
                pdf_url=pdf_url,
                published_date=article.get("publication_date"),
                tldr=None,
                fields_of_study=[],
                query_variant_matched=[query],
            ))

        return papers

    # ──────────────────────────────────────────────────────────────────────────
    # OpenAlex Search (optional - only runs when OPENALEX_API_KEY is set)
    # ──────────────────────────────────────────────────────────────────────────

    async def _safe_openalex_search(
        self, client: httpx.AsyncClient, query: str
    ) -> list[PaperResult]:
        try:
            return await self._search_openalex(client, query)
        except Exception as e:
            logger.warning("OpenAlex search failed for '%s': %s", query, e)
            return []

    @staticmethod
    def _openalex_clean_query(query: str) -> str:
        """OpenAlex rejects wildcard characters (? *) in stemmed search with HTTP 400, and treats
        quotes and uppercase AND/OR/NOT as operators. Natural-language queries often contain them."""
        text = re.sub(r'[?*"~]', " ", query)
        text = re.sub(r"\b(AND|OR|NOT)\b", lambda m: m.group(0).lower(), text)
        return re.sub(r"\s+", " ", text).strip()

    def _openalex_or_query(self, query: str) -> str:
        """Content words joined with OR. Plain keyword search requires *every* word to match, which
        returns nothing for long natural-language queries; OR gives broad recall and the reranker
        then orders the candidates."""
        words = [
            w for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9\-‑]*", query)
            if w.lower() not in self.OPENALEX_STOPWORDS and len(w) > 1
        ]
        words = list(dict.fromkeys(words))
        return " OR ".join(words) if len(words) >= 2 else query

    async def _search_openalex(
        self, client: httpx.AsyncClient, query: str
    ) -> list[PaperResult]:
        """Search OpenAlex /works for relevant papers. Returns [] when no key is configured.

        Runs up to two complementary searches concurrently and returns the union (the caller dedupes):
          - AI-reranked keyword search: OR-joined content words, top 100 reordered by an answer-relevance model
          - semantic search: embedding match on the whole query (favours established, well-cited papers)
        """
        if self._openalex_pool is None:
            return []

        clean = self._openalex_clean_query(query)
        if not clean:
            return []

        filters = [self.OPENALEX_BASE_FILTER]
        if self.min_citations > 0:
            filters.append(f"cited_by_count:>{self.min_citations - 1}")
        common = {
            "filter": ",".join(filters),
            "per_page": min(self.max_results, 100),
            "select": self.OPENALEX_SELECT,
        }

        searches = []
        if self.openalex_rerank:
            searches.append({**common, "search.title_abstract_keywords": self._openalex_or_query(clean),
                             "rerank": "true"})
        else:
            searches.append({**common, "search.title_abstract_keywords": self._openalex_or_query(clean)})
        if self.openalex_semantic:
            searches.append({**common, "search.semantic": clean})

        batches = await asyncio.gather(
            *(self._openalex_request(client, params, query) for params in searches),
            return_exceptions=True,
        )
        papers: list[PaperResult] = []
        for batch in batches:
            if isinstance(batch, Exception):
                logger.warning("OpenAlex search failed for '%s': %s", query[:60], type(batch).__name__)
            else:
                papers.extend(batch)
        return papers

    async def _openalex_request(
        self, client: httpx.AsyncClient, params: dict, query: str
    ) -> list[PaperResult]:
        """One OpenAlex call with key rotation and backoff.

        Keys rotate through a KeyPool: a key whose daily budget is spent (or that is rejected)
        is parked and the next key is used; short 429 bursts back off exponentially."""
        pool = self._openalex_pool

        max_backoffs = self.openalex_max_attempts
        backoffs = 0
        for _ in range(max_backoffs + 2 * len(pool) + 2):  # hard cap on total loop turns
            key = pool.get_key()
            if key is None:
                # every key is cooling down: wait it out if short, otherwise OpenAlex is out for now
                wait = pool.next_available_in()
                if wait > self.openalex_backoff_cap or backoffs >= max_backoffs:
                    if not self._openalex_warned:
                        logger.warning("No usable OpenAlex keys (next available in %.0fs) - skipping OpenAlex", wait)
                        self._openalex_warned = True
                    return []
                backoffs += 1
                await asyncio.sleep(wait + 0.1)
                continue

            await self._openalex_limiter.acquire()
            try:
                # Key goes in a header, not the query string, so it never shows up in httpx's URL logging.
                resp = await client.get(self.OPENALEX_API_URL, params=params,
                                        headers={"Authorization": f"Bearer {key}"},
                                        timeout=self.openalex_timeout)
            except httpx.TransportError as e:
                backoffs += 1
                if backoffs >= max_backoffs:
                    raise
                await asyncio.sleep(2 ** backoffs)
                logger.debug("OpenAlex transport error, retrying: %s", e)
                continue

            tag = f"key ...{key[-4:]}"
            if resp.status_code in (401, 403):
                logger.warning("OpenAlex rejected %s (HTTP %d) - removing it from rotation", tag, resp.status_code)
                pool.mark_rate_limited(key, seconds=10 * 365 * 86400)
                continue

            if resp.status_code == 429 and self._openalex_budget_spent(resp):
                reset = float(resp.headers.get("x-ratelimit-reset", "0") or 0)
                logger.warning("OpenAlex %s: daily budget exhausted (resets in %.0fs), rotating", tag, reset)
                pool.mark_rate_limited(key, seconds=min(reset, 86400))
                continue

            if resp.status_code == 429 or resp.status_code >= 500:
                wait = min(self.openalex_backoff_cap, self.openalex_backoff_base * 2 ** backoffs)
                wait += random.uniform(0, wait * 0.25)
                retry_after = resp.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    wait = max(wait, float(retry_after))
                backoffs += 1
                if backoffs >= max_backoffs:
                    logger.warning("OpenAlex gave up on '%s' after %d backoffs (last status %d)",
                                   query[:60], backoffs, resp.status_code)
                    return []
                logger.warning("OpenAlex %d on %s for '%s' (backoff %d/%d), pausing that key %.1fs",
                               resp.status_code, tag, query[:60], backoffs, max_backoffs, wait)
                pool.mark_rate_limited(key, seconds=wait)
                # another key may be free right now; otherwise the next turn waits for the earliest one
                idle = pool.next_available_in()
                if idle > 0:
                    await asyncio.sleep(idle)
                continue

            resp.raise_for_status()
            return self._parse_openalex_results(resp.json().get("results", []), query)

        return []

    def _openalex_budget_spent(self, resp: httpx.Response) -> bool:
        """True when a 429 means the daily credit budget is gone (not a short per-second burst)."""
        remaining = resp.headers.get("x-ratelimit-remaining", "")
        reset = resp.headers.get("x-ratelimit-reset", "")
        return remaining == "0" and reset.isdigit() and float(reset) > self.openalex_backoff_cap

    @staticmethod
    def _openalex_abstract(inverted_index: Optional[dict]) -> str:
        """OpenAlex ships abstracts as {word: [positions]}; rebuild the text."""
        if not inverted_index:
            return ""
        words = [(pos, word) for word, positions in inverted_index.items() for pos in positions]
        return " ".join(word for _, word in sorted(words))

    def _parse_openalex_results(self, works: list[dict], query: str) -> list[PaperResult]:
        results = []
        for w in works:
            title = (w.get("title") or "").strip()
            abstract = self._openalex_abstract(w.get("abstract_inverted_index"))
            if not title or not abstract:
                continue

            doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", (w.get("doi") or "").strip(), flags=re.I).lower() or None

            primary = w.get("primary_location") or {}
            best_oa = w.get("best_oa_location") or {}
            oa = w.get("open_access") or {}

            # arXiv ID: arXiv DOIs look like 10.48550/arxiv.2410.12119; repositories link arxiv.org/abs/<id>
            arxiv_id = None
            for text in (doi or "", primary.get("landing_page_url") or "", best_oa.get("landing_page_url") or ""):
                m = re.search(r"arxiv(?:\.org/abs/|\.)(\d{4}\.\d{4,5})", text, flags=re.I)
                if m:
                    arxiv_id = m.group(1)
                    break

            pdf_url = best_oa.get("pdf_url") or primary.get("pdf_url") or (oa.get("oa_url") if oa.get("is_oa") else None)

            source_info = primary.get("source") or {}
            is_repository = source_info.get("type") == "repository"
            venue = None if is_repository else source_info.get("display_name")

            fields = []
            for t in w.get("topics") or []:
                name = (t.get("field") or {}).get("display_name")
                if name and name not in fields:
                    fields.append(name)

            results.append(PaperResult(
                title=title,
                abstract=abstract,
                authors=[
                    (a.get("author") or {}).get("display_name", "Unknown")
                    for a in (w.get("authorships") or [])
                ],
                year=w.get("publication_year"),
                venue=venue,
                citation_count=w.get("cited_by_count"),
                influential_citation_count=None,
                is_preprint=w.get("type") == "preprint" or not venue,
                source="openalex",
                arxiv_id=arxiv_id,
                doi=doi,
                pdf_url=pdf_url,
                published_date=w.get("publication_date"),
                tldr=None,
                fields_of_study=fields[:3],
                query_variant_matched=[query],
            ))
        return results

    # ──────────────────────────────────────────────────────────────────────────
    # Deduplication
    # ──────────────────────────────────────────────────────────────────────────

    def _merge_and_dedupe(self, papers: list[PaperResult]) -> list[PaperResult]:
        """
        Deduplicate papers by arXiv ID, DOI, or normalized title (any match merges).

        A paper is registered under every identifier it has, so a match on any one of
        them finds it. On a duplicate we combine query_variant_matched, mark the source
        as "both" when different APIs returned it, and fill in metadata the first copy lacked.
        """
        index: dict[str, PaperResult] = {}
        unique: list[PaperResult] = []

        for paper in papers:
            keys = self._dedupe_keys(paper)
            existing = next((index[k] for k in keys if k in index), None)

            if existing is None:
                unique.append(paper)
                existing = paper
            else:
                self._merge_into(existing, paper)

            for k in self._dedupe_keys(existing) + keys:
                index.setdefault(k, existing)

        # Sort by citation count (descending), then year
        unique.sort(
            key=lambda p: (p.citation_count or 0, p.year or 0),
            reverse=True,
        )
        return unique

    @staticmethod
    def _merge_into(existing: PaperResult, paper: PaperResult) -> None:
        existing.query_variant_matched = list(
            dict.fromkeys(existing.query_variant_matched + paper.query_variant_matched)
        )
        if existing.source != paper.source:
            existing.source = "both"

        # Fill gaps left by the first copy
        for field in ("arxiv_id", "doi", "pdf_url", "venue", "published_date", "tldr", "year"):
            if not getattr(existing, field) and getattr(paper, field):
                setattr(existing, field, getattr(paper, field))
        if not existing.abstract and paper.abstract:
            existing.abstract = paper.abstract
        if not existing.fields_of_study and paper.fields_of_study:
            existing.fields_of_study = paper.fields_of_study
        if existing.venue and paper.venue:
            existing.is_preprint = existing.is_preprint and paper.is_preprint

        # Citation counts differ between providers; keep the highest known value
        if paper.citation_count is not None:
            existing.citation_count = max(existing.citation_count or 0, paper.citation_count)
        if paper.influential_citation_count is not None:
            existing.influential_citation_count = max(
                existing.influential_citation_count or 0, paper.influential_citation_count
            )

    def _dedupe_keys(self, paper: PaperResult) -> list[str]:
        """All identifiers a paper can be matched on (arXiv ID, DOI, normalized title)."""
        keys = []
        if paper.arxiv_id:
            keys.append("arxiv:" + re.sub(r"v\d+$", "", paper.arxiv_id.strip().lower()))
        if paper.doi:
            doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", paper.doi.strip().lower())
            keys.append("doi:" + doi)
        title = self._norm_title(paper.title)
        if title:
            keys.append("title:" + title)
        return keys

    @staticmethod
    def _norm_title(title: str) -> str:
        """Normalize title for fuzzy matching: lowercase, strip punctuation."""
        import re
        text = title.lower().strip()
        text = re.sub(r"[^\w\s]", "", text)
        text = re.sub(r"\s+", " ", text)
        return text

    async def _enrich_citation_counts(
        self, client: httpx.AsyncClient, papers: list[PaperResult]
    ) -> None:
        """Fetch citation counts from Semantic Scholar for papers missing them."""
        arxiv_only = [
            p for p in papers
            if p.arxiv_id and p.citation_count is None
        ]
        if not arxiv_only:
            return

        logger.info("Citation enrichment: %d arXiv-only papers to enrich", len(arxiv_only))

        headers = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        for i in range(0, len(arxiv_only), 10):
            batch = arxiv_only[i:i+10]
            ids = []
            valid_batch = []
            for p in batch:
                arxiv_id = p.arxiv_id.strip()
                arxiv_id = re.sub(r'v\d+$', '', arxiv_id)
                if not re.match(r'^\d{4}\.\d{4,5}$', arxiv_id):
                    logger.debug("Skipping invalid arXiv ID: %s", arxiv_id)
                    continue
                ids.append(f"ARXIV:{arxiv_id}")
                valid_batch.append(p)

            if not ids:
                continue

            logger.info("S2 batch enrichment: sending %d IDs: %s", len(ids), ids[:3])
            for attempt in range(3):
                try:
                    await asyncio.sleep(10 if not self.api_key else 1)
                    await self._s2_limiter.acquire()
                    resp = await client.post(
                        f"{self.SEMANTIC_SCHOLAR_URL}/paper/batch",
                        json={"ids": ids},
                        params={"fields": "citationCount,influentialCitationCount"},
                        headers=headers,
                    )
                    logger.info("S2 batch response: status=%d, body=%s", resp.status_code, resp.text[:200])
                    if resp.status_code == 429:
                        wait = 2 ** attempt * 5
                        logger.warning("S2 rate limited on batch, backing off %ds", wait)
                        await asyncio.sleep(wait)
                        continue
                    if resp.status_code in (500, 502, 503):
                        wait = 2 ** attempt * 2
                        await asyncio.sleep(wait)
                        continue
                    if resp.status_code == 400:
                        logger.error("S2 batch 400 error: %s", resp.text[:300])
                        break
                    resp.raise_for_status()
                    results = resp.json()

                    for paper, s2_data in zip(valid_batch, results):
                        if s2_data:
                            paper.citation_count = s2_data.get("citationCount")
                            paper.influential_citation_count = s2_data.get("influentialCitationCount")
                    break
                except Exception as e:
                    if attempt == 2:
                        logger.warning("Failed to enrich citation counts after 3 attempts: %s", e)
                    else:
                        await asyncio.sleep(2 ** attempt * 2)


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
