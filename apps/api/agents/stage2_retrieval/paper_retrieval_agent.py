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
from types import SimpleNamespace
from typing import Optional

import httpx
from pydantic import BaseModel, Field

from apps.api.agents.stage2_retrieval.key_pool import KeyPool
from apps.api.agents.stage2_retrieval.markdown_parser import PARSER_VERSION, clean_abstract, parse_markdown
from apps.api.services import db_service, trace_llm_service

# PDFs larger than this are skipped (a 59 MB file held a Docling worker for ~2 minutes and then failed). 0 = no cap.
MAX_PDF_SIZE_MB = float(os.getenv("MAX_PDF_SIZE_MB", "20"))

# Docling request settings. OCR off by default (see _parse_with_docling); set DOCLING_DO_OCR=true to always OCR.
DOCLING_DO_OCR = os.getenv("DOCLING_DO_OCR", "false").lower() in ("1", "true", "yes")
DOCLING_OCR_RETRY_BELOW_CHARS = 500     # fewer characters than this without OCR = probably a scanned PDF
DOCLING_TIMEOUT_SECONDS = float(os.getenv("DOCLING_TIMEOUT_SECONDS", "300"))


def _docling_markdown(data: dict) -> str:
    document = data.get("document") or {}
    return document.get("md_content") or data.get("md_content") or ""


# PDF failure memory: a paper whose PDF could not be fetched for a lasting reason (HTTP 403 / 404 / 410 / 451, an HTML
# landing page, an over-size file) is skipped for this many days instead of repeating the whole download-and-fallback chain
# every run (16 of 40 failures in the logs were repeats). 0 turns it off. Bump DOWNLOADER_VERSION whenever the download
# logic improves: failures recorded by an older version are then ignored.
PDF_FAILURE_TTL_DAYS = float(os.getenv("PDF_FAILURE_TTL_DAYS", "7"))
DOWNLOADER_VERSION = 2          # 2 = first-bytes PDF check + landing-page citation_pdf_url
LASTING_HTTP_STATUS = (403, 404, 410, 451)
LANDING_PAGE_BYTES = 600_000     # how much of an HTML landing page is read when looking for its PDF address

# Parse cache: reuse a stored parse of the same paper (see PaperRetrievalAgent._parse_single_paper).
PARSE_CACHE_ENABLED = os.getenv("PARSE_CACHE", "true").lower() not in ("0", "false", "no")
PARSE_CACHE_MIN_CHARS = 3000        # a stored row counts as a real parse above this many characters of full text


class S2Unavailable(Exception):
    """Semantic Scholar search gave up (HTTP 429 / 5xx after the allowed attempts)."""


class PdfTooLargeError(Exception):
    """The PDF is over MAX_PDF_SIZE_MB; no other source is tried because it would be the same file."""

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
    source: str = "arxiv"  # "arxiv" | "semantic_scholar" | "ieee" | "openalex" | "scopus" | "both"
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
        # Requests in flight at once, across all sub-questions: 9 queries x 2 searches fired together drew 429 bursts
        # even though the per-second rate was fine. Backoff sleeps happen outside the semaphore.
        self.openalex_max_concurrent = max(1, int(os.getenv("OPENALEX_MAX_CONCURRENT", "2")))
        self._openalex_semaphore = asyncio.Semaphore(self.openalex_max_concurrent)
        self._parse_in_flight: dict[str, asyncio.Future] = {}   # paper key -> parse running in this run
        self._download_failures: dict[str, tuple[str, str]] = {}  # retrieved_paper_id -> (error class, detail) of the last terminal failure

        # Scopus (optional): searched through the host, which has the entitlement to abstracts. Switched off for the rest
        # of the run as soon as the host says it cannot serve it (endpoint missing, no key, no abstracts).
        self.scopus_enabled = os.getenv("SCOPUS_ENABLED", "true").lower() not in ("0", "false", "no")
        self.scopus_results = min(max(int(os.getenv("SCOPUS_RESULTS_PER_QUERY", "25")), 1), 25)   # one page; COMPLETE allows 25
        self.scopus_min_year = int(os.getenv("SCOPUS_MIN_YEAR", "0"))                              # 0 = no year filter
        self._scopus_semaphore = asyncio.Semaphore(max(1, int(os.getenv("SCOPUS_MAX_CONCURRENT", "3"))))
        self._scopus_disabled: str | None = None

        # Semantic Scholar SEARCH circuit breaker. Without an API key, nearly every search request is rate limited (3 of 110
        # succeeded over six runs) and the 10 s limiter spacing made the failing calls cost about 3 minutes per run.
        #   S2_SEARCH=auto (default): the first search is a single-attempt probe; if it fails (429 / 5xx / network) Semantic
        #       Scholar search is skipped for the rest of the run, including calls already waiting; if it works, searching
        #       continues with the normal retries, and S2_TRIP_AFTER consecutive give-ups trip the breaker too.
        #   S2_SEARCH=off: never search Semantic Scholar.   S2_SEARCH=on: always search (no breaker).
        # Citation enrichment (a different endpoint, used after the relevance filter) is not affected.
        self.s2_mode = os.getenv("S2_SEARCH", "auto").strip().lower()
        if self.s2_mode not in ("auto", "off", "on"):
            logger.warning("Unknown S2_SEARCH=%r, using auto", self.s2_mode)
            self.s2_mode = "auto"
        self.s2_trip_after = max(1, int(os.getenv("S2_TRIP_AFTER", "3")))
        self._s2_tripped = False
        self._s2_probe_started = False
        self._s2_probe_done = asyncio.Event()
        self._s2_giveups = 0

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

    @staticmethod
    def _paper_key(paper_metadata: dict) -> str:
        """Identity of a paper across queries: arXiv id, else DOI, else normalised title."""
        return db_service.paper_key(paper_metadata)

    async def _parse_single_paper(self, retrieved_paper_id: str) -> Optional[ParsedPaper]:
        """Parse one paper, reusing an earlier parse of the same paper when there is one.

        1. If another task of this run is parsing the same paper right now, wait for it (so a paper kept under two
           sub-questions is downloaded once).
        2. Look for a stored parse of the same paper (any earlier query, current parser version, real full text) and
           copy it under this retrieved_paper_id - no download, no Docling, no PDFFigures.
        3. Otherwise download and parse as usual."""
        paper_metadata = await asyncio.to_thread(db_service.get_retrieved_paper, retrieved_paper_id)
        if not paper_metadata:
            logger.warning("Paper not found: %s", retrieved_paper_id)
            return None
        if not PARSE_CACHE_ENABLED:
            return await self._parse_guarded(retrieved_paper_id, paper_metadata)

        key = self._paper_key(paper_metadata)
        in_flight = self._parse_in_flight.get(key)
        if in_flight is not None:
            try:
                await asyncio.shield(in_flight)
            except Exception:
                pass                                    # the other parse failed; fall through and try ourselves

        # register BEFORE the first await below, so a second task for the same paper sees us and waits
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._parse_in_flight[key] = future
        try:
            cached = await self._load_cached_parse(retrieved_paper_id, paper_metadata)
            if cached is not None:
                return cached
            return await self._parse_guarded(retrieved_paper_id, paper_metadata)
        finally:
            self._parse_in_flight.pop(key, None)
            future.set_result(None)

    @staticmethod
    def _lasting_failure(error: Exception | None) -> tuple[str, str] | None:
        """(error class, detail) when the failure will not fix itself, else None (timeouts, connection errors, 429, 5xx may succeed later)."""
        if isinstance(error, httpx.HTTPStatusError) and error.response is not None and error.response.status_code in LASTING_HTTP_STATUS:
            return f"HTTP {error.response.status_code}", str(error)[:200]
        if isinstance(error, ValueError) and "Non-PDF response" in str(error):
            return "html or non-PDF response", str(error)[:200]
        if isinstance(error, PdfTooLargeError):
            return "pdf over the size cap", str(error)[:200]
        return None

    async def _parse_guarded(self, retrieved_paper_id: str, paper_metadata: dict) -> Optional[ParsedPaper]:
        """Download-and-parse with the PDF failure memory: skip a paper that failed lastingly in the last PDF_FAILURE_TTL_DAYS days,
        remember a new lasting failure, forget a failure when the paper now parses."""
        key = self._paper_key(paper_metadata)
        if PDF_FAILURE_TTL_DAYS > 0:
            known = await asyncio.to_thread(db_service.get_pdf_failures, [key], PDF_FAILURE_TTL_DAYS, DOWNLOADER_VERSION)
            if key in known:
                row = known[key]
                logger.info("Skipping '%s': its PDF failed before (%s, %sx); retried after %.0f days or when the download logic improves",
                            (paper_metadata.get("title") or "")[:60], row.get("error_class"), row.get("fail_count"), PDF_FAILURE_TTL_DAYS)
                return self._empty_parsed(retrieved_paper_id, paper_metadata)

        result = await self._parse_single_paper_uncached(retrieved_paper_id, paper_metadata)

        if PDF_FAILURE_TTL_DAYS > 0:
            failure = self._download_failures.pop(retrieved_paper_id, None)
            if failure:
                await asyncio.to_thread(db_service.record_pdf_failure, key, paper_metadata.get("title") or "",
                                        paper_metadata.get("doi"), failure[0], failure[1], DOWNLOADER_VERSION)
            elif result is not None and len(result.full_text or "") >= PARSE_CACHE_MIN_CHARS:
                await asyncio.to_thread(db_service.clear_pdf_failure, key)
        return result

    async def _load_cached_parse(self, retrieved_paper_id: str, paper_metadata: dict) -> Optional[ParsedPaper]:
        try:
            row = await asyncio.to_thread(
                db_service.find_cached_parse, paper_metadata, PARSER_VERSION, PARSE_CACHE_MIN_CHARS)
        except Exception as e:                          # a cache problem must never block parsing
            logger.warning("Parse cache lookup failed for %s: %s: %s", retrieved_paper_id, type(e).__name__, e)
            return None
        if row is None:
            return None

        parsed = ParsedPaper(
            retrieved_paper_id=retrieved_paper_id,
            title=row.get("title") or "",
            authors=row.get("authors") or [],
            abstract=row.get("abstract") or "",
            sections=[Section(heading=s.get("heading", ""), text=s.get("text", ""), level=s.get("level", 1))
                      for s in (row.get("sections") or [])],
            references=row.get("cited_references") or [],
            figures=[Figure(label=f.get("label", ""), caption=f.get("caption", ""),
                            image_path=f.get("image_path"), page=f.get("page"))
                     for f in (row.get("figures") or [])],
            full_text=row.get("full_text") or "",
        )
        self._apply_metadata(parsed, paper_metadata)
        await asyncio.to_thread(self._store_parsed_paper, parsed)
        logger.info("Parse cache hit: '%s' (%d chars) reused from an earlier query - no download or parsing",
                    (paper_metadata.get("title") or "")[:60], len(parsed.full_text))
        return parsed

    async def _parse_single_paper_uncached(self, retrieved_paper_id: str, paper_metadata: dict) -> Optional[ParsedPaper]:
        """Download and parse one paper (Docling + PDFFigures), with the URL / Unpaywall / Playwright fallbacks."""
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
                    self._apply_metadata(docling_result, paper_metadata)
                    docling_result.figures = figures if isinstance(figures, list) else []

                    self._store_parsed_paper(docling_result)
                    return docling_result

            except PdfTooLargeError as e:
                logger.warning("Skipping oversized PDF for %s: %s", retrieved_paper_id, e)
                self._download_failures[retrieved_paper_id] = self._lasting_failure(e)
                return self._empty_parsed(retrieved_paper_id, paper_metadata)
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
                        self._apply_metadata(docling_result, paper_metadata)
                        docling_result.figures = figures if isinstance(figures, list) else []

                        self._store_parsed_paper(docling_result)
                        return docling_result
            except PdfTooLargeError as e:
                logger.warning("Skipping oversized PDF for %s: %s", retrieved_paper_id, e)
                return self._empty_parsed(retrieved_paper_id, paper_metadata)
            except Exception as e:
                logger.warning("Unpaywall fallback failed for %s: %s: %r", doi, type(e).__name__, e)

        pdf_url = pdf_urls[0] if pdf_urls else None
        if pdf_url:
            try:
                pdf_bytes = await self._download_pdf_playwright(pdf_url)
                if pdf_bytes and MAX_PDF_SIZE_MB > 0 and len(pdf_bytes) > MAX_PDF_SIZE_MB * 1048576:
                    logger.warning("Skipping oversized PDF for %s: %.1f MB exceeds the %s MB cap",
                                   retrieved_paper_id, len(pdf_bytes) / 1048576, MAX_PDF_SIZE_MB)
                    return self._empty_parsed(retrieved_paper_id, paper_metadata)
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
                        self._apply_metadata(docling_result, paper_metadata)
                        docling_result.figures = figures if isinstance(figures, list) else []

                        self._store_parsed_paper(docling_result)
                        return docling_result
            except Exception as e:
                logger.warning("Playwright fallback failed: %s: %r", type(e).__name__, e)

        logger.error("All PDF URLs failed for %s: %s: %r", retrieved_paper_id, type(last_error).__name__ if last_error else "None", last_error)
        lasting = self._lasting_failure(last_error)
        if lasting:
            self._download_failures[retrieved_paper_id] = lasting
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

    @staticmethod
    def _empty_parsed(retrieved_paper_id: str, paper_metadata: dict) -> ParsedPaper:
        """Metadata-only result (nothing stored) for a paper whose PDF was skipped."""
        return ParsedPaper(
            retrieved_paper_id=retrieved_paper_id,
            title=paper_metadata.get("title", ""),
            authors=paper_metadata.get("authors", []),
            abstract=paper_metadata.get("abstract", ""),
            sections=[], references=[], figures=[], full_text="",
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
            parser_version=PARSER_VERSION,
        )

    @staticmethod
    def _pdf_links_in_html(html: str, base_url: str) -> list[str]:
        """PDF addresses a landing page announces: <meta name="citation_pdf_url" content="..."> and <link type="application/pdf" href="...">."""
        from urllib.parse import urljoin
        links = []
        for m in re.finditer(r"<meta[^>]+>", html, flags=re.I):
            tag = m.group(0)
            if re.search(r'name=["\']citation_pdf_url["\']', tag, flags=re.I):
                c = re.search(r'content=["\']([^"\']+)["\']', tag, flags=re.I)
                if c:
                    links.append(urljoin(base_url, c.group(1).replace("&amp;", "&")))
        for m in re.finditer(r'<link[^>]+type=["\']application/pdf["\'][^>]*>', html, flags=re.I):
            h = re.search(r'href=["\']([^"\']+)["\']', m.group(0), flags=re.I)
            if h:
                links.append(urljoin(base_url, h.group(1)))
        return list(dict.fromkeys(links))

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

        max_bytes = MAX_PDF_SIZE_MB * 1024 * 1024 if MAX_PDF_SIZE_MB > 0 else 0

        async def _fetch(target: str) -> tuple[int, str, bytes, str]:
            """(status, kind, body, final url). kind is 'pdf' or 'html', decided by the first bytes ('%PDF-'), not by the
            content-type (some servers send PDFs as application/octet-stream). Streams the body so an oversized PDF is abandoned
            as soon as it is known to be too big; an HTML page is read only up to LANDING_PAGE_BYTES."""
            async with client.stream("GET", target, follow_redirects=True, headers=headers) as resp:
                if resp.status_code >= 400:
                    if resp.status_code == 403:
                        return 403, "", b"", target
                    resp.raise_for_status()
                content_type = resp.headers.get("content-type", "").lower()
                declared = int(resp.headers.get("content-length") or 0)
                if max_bytes and declared > max_bytes and "html" not in content_type:
                    raise PdfTooLargeError(f"{declared / 1048576:.1f} MB exceeds the {MAX_PDF_SIZE_MB} MB cap")
                chunks, size, kind = [], 0, None
                async for chunk in resp.aiter_bytes():
                    if kind is None:
                        start = chunk.lstrip()[:5]
                        if start == b"%PDF-":
                            kind = "pdf"
                        elif "html" in content_type or start[:1] == b"<":
                            kind = "html"
                        else:
                            raise ValueError(f"Non-PDF response (content-type: {content_type}) for {url[:80]}")
                    size += len(chunk)
                    if kind == "pdf" and max_bytes and size > max_bytes:
                        raise PdfTooLargeError(f"over the {MAX_PDF_SIZE_MB} MB cap (download stopped at {size / 1048576:.1f} MB)")
                    chunks.append(chunk)
                    if kind == "html" and size >= LANDING_PAGE_BYTES:
                        break
                if kind is None:
                    raise ValueError(f"Non-PDF response (content-type: {content_type}) for {url[:80]}")
                return resp.status_code, kind, b"".join(chunks), str(resp.url)

        status, kind, body, final_url = await _fetch(url)
        if status == 403 and "?" in url:
            clean_url = url.split("?")[0]
            logger.info("Retrying without query params: %s", clean_url)
            status, kind, body, final_url = await _fetch(clean_url)
        if status == 403:
            raise httpx.HTTPStatusError("403 Forbidden", request=httpx.Request("GET", url), response=httpx.Response(403))

        if kind == "html":
            # a landing page: most publishers and repositories name the PDF in <meta name="citation_pdf_url">
            for link in self._pdf_links_in_html(body.decode("utf-8", "replace"), final_url)[:2]:
                if link == url:
                    continue
                try:
                    link_status, link_kind, link_body, _ = await _fetch(link)
                except PdfTooLargeError:
                    raise
                except Exception as e:
                    logger.info("citation_pdf_url %s failed: %s", link[:80], str(e)[:80])
                    continue
                if link_status == 200 and link_kind == "pdf":
                    logger.info("Found the PDF through the landing page's citation_pdf_url: %s", link[:100])
                    body = link_body
                    break
            else:
                raise ValueError(f"Non-PDF response (content-type: text/html) for {url[:80]}")

        logger.info("Downloaded PDF: %d bytes", len(body))
        return body

    async def _parse_with_docling(self, pdf_bytes: bytes) -> ParsedPaper:
        """Parse PDF using Docling Docker API for metadata, sections, and references."""
        import base64
        
        b64_data = base64.b64encode(pdf_bytes).decode("utf-8")
        logger.info("Parsing PDF with Docling Docker API (%d bytes)", len(pdf_bytes))

        async def convert(do_ocr: bool) -> dict:
            async with httpx.AsyncClient(timeout=DOCLING_TIMEOUT_SECONDS) as client:
                resp = await client.post(
                    f"{self.docling_url}/v1/convert/source",
                    json={
                        "sources": [{"kind": "file", "base64_string": b64_data, "filename": "paper.pdf"}],
                        "options": {"to_formats": ["md"], "do_ocr": do_ocr, "include_images": False},
                    },
                )
                resp.raise_for_status()
                return resp.json()

        # Born-digital papers have a text layer, so OCR (the slowest step: 2.2x on the benchmark papers, identical
        # Markdown) is skipped. A scanned PDF comes back nearly empty and is retried once with OCR on.
        data = await convert(do_ocr=DOCLING_DO_OCR)
        if not DOCLING_DO_OCR and len(_docling_markdown(data).strip()) < DOCLING_OCR_RETRY_BELOW_CHARS:
            logger.info("Docling returned little text without OCR (scanned PDF?) - retrying with OCR")
            data = await convert(do_ocr=True)

        document = data.get("document", {})
        md_content = ""

        if document and "md_content" in document:
            md_content = document["md_content"] or ""
        elif "md_content" in data:
            md_content = data["md_content"] or ""

        if not md_content or len(md_content.strip()) < 50:
            raise ValueError("Docling returned empty or minimal content")

        parsed = parse_markdown(md_content)
        title = parsed.title or document.get("title") or data.get("title") or "Unknown"

        return ParsedPaper(
            retrieved_paper_id="",
            title=title,
            authors=parsed.authors,
            abstract=parsed.abstract,
            sections=[Section(heading=sec["heading"], text=sec["text"], level=sec["level"]) for sec in parsed.sections],
            references=parsed.references,
            figures=[],
            full_text=md_content,
        )

    @staticmethod
    def _apply_metadata(parsed: "ParsedPaper", paper_metadata: dict) -> None:
        """API metadata is cleaner than what can be recovered from a PDF's first page, so it wins for title, authors
        and abstract; the parsed values only fill gaps. Sections, references and full text always come from the parse."""
        title = (paper_metadata.get("title") or "").strip()
        if title:
            parsed.title = title
        authors = [a for a in (paper_metadata.get("authors") or []) if a]
        if authors:
            parsed.authors = authors
        abstract = clean_abstract(paper_metadata.get("abstract") or "")
        if len(abstract) >= 100 or not parsed.abstract:
            parsed.abstract = abstract or parsed.abstract

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
        enrich: bool = True,
    ) -> list[dict]:
        """
        Search all query variants concurrently across both APIs.

        Args:
            sub_question: The research sub-question being investigated.
            query_variants: Paraphrased/reformulated search queries.
            enrich: fetch Semantic Scholar citation counts (and apply min_citations) now. The pipeline passes False
                and calls enrich_papers() after the relevance filter, so only the kept papers are enriched.

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
                if self.scopus_enabled and not self._scopus_disabled:
                    tasks.append(self._safe_scopus_search(query))

            results = await asyncio.gather(*tasks, return_exceptions=False)

        # Flatten and deduplicate
        all_papers: list[PaperResult] = []
        for paper_list in results:
            all_papers.extend(paper_list)

        merged = self._merge_and_dedupe(all_papers)

        if enrich:
            async with httpx.AsyncClient(timeout=30.0) as client:
                await self._enrich_citation_counts(client, merged)

            if self.min_citations > 0:
                merged = [p for p in merged if (p.citation_count or 0) >= self.min_citations]

        return [p.model_dump() for p in merged]

    async def enrich_papers(self, papers: list[dict]) -> list[dict]:
        """Citation counts from Semantic Scholar for paper dicts (in place), then the min_citations filter.

        Meant to run after the relevance filter: the counts only feed the reliability score, so fetching them for
        candidates that are about to be dropped just spends the rate-limited Semantic Scholar budget. A paper kept
        under several sub-questions is looked up once."""
        by_arxiv: dict[str, list[dict]] = {}
        for p in papers:
            if p.get("arxiv_id") and p.get("citation_count") is None:
                by_arxiv.setdefault(p["arxiv_id"], []).append(p)

        if by_arxiv:
            stand_ins = {aid: SimpleNamespace(arxiv_id=aid, citation_count=None, influential_citation_count=None)
                         for aid in by_arxiv}
            async with httpx.AsyncClient(timeout=30.0) as client:
                await self._enrich_citation_counts(client, list(stand_ins.values()))
            for aid, rows in by_arxiv.items():
                for row in rows:
                    row["citation_count"] = stand_ins[aid].citation_count
                    row["influential_citation_count"] = stand_ins[aid].influential_citation_count

        if self.min_citations > 0:
            papers = [p for p in papers if (p.get("citation_count") or 0) >= self.min_citations]
        return papers

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
        """Semantic Scholar search for one query, behind the circuit breaker described in __init__ (S2_SEARCH)."""
        if self.s2_mode == "off" or self._s2_tripped:
            return []

        if self.s2_mode == "auto":
            if not self._s2_probe_started:
                self._s2_probe_started = True             # this call is the probe: one attempt, no backoff
                try:
                    papers = await self._search_semantic_scholar(client, query, max_attempts=1)
                    self._s2_giveups = 0
                    return papers
                except Exception as e:                    # 429 / 5xx / network: not usable right now
                    self._s2_tripped = True
                    logger.warning("Semantic Scholar probe failed (%s): skipping Semantic Scholar search for this run",
                                   str(e)[:100])
                    return []
                finally:
                    self._s2_probe_done.set()
            await self._s2_probe_done.wait()              # callers queued behind the probe cost nothing while it runs
            if self._s2_tripped:
                return []

        try:
            papers = await self._search_semantic_scholar(client, query)
            self._s2_giveups = 0
            return papers
        except S2Unavailable:
            self._s2_giveups += 1
            if self.s2_mode == "auto" and self._s2_giveups >= self.s2_trip_after and not self._s2_tripped:
                self._s2_tripped = True
                logger.warning("Semantic Scholar gave up %d searches in a row: skipping it for the rest of this run",
                               self._s2_giveups)
            return []
        except Exception as e:
            logger.warning("Semantic Scholar search failed for '%s': %s", query, e)
            return []

    async def _search_semantic_scholar(
        self, client: httpx.AsyncClient, query: str, max_attempts: int | None = None
    ) -> list[PaperResult]:
        """Search Semantic Scholar /paper/search endpoint. Raises S2Unavailable when it gives up on 429 / 5xx."""
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

        max_attempts = max_attempts or self.s2_max_attempts
        for attempt in range(max_attempts):
            # Every attempt (not just the first) goes through the shared limiter.
            await self._s2_limiter.acquire()
            if self.s2_mode == "auto" and self._s2_tripped and max_attempts != 1:
                return []                                   # tripped while this call waited its turn: send nothing
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
            raise S2Unavailable(f"HTTP {resp.status_code}")

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

            try:
                async with self._openalex_semaphore:
                    await self._openalex_limiter.acquire()
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

    # ──────────────────────────────────────────────────────────────────────────
    # Scopus Search (optional - through the host, see infra/query_generator/scopus_router.py)
    # ──────────────────────────────────────────────────────────────────────────

    SCOPUS_RESERVED = frozenset({"and", "or", "not", "near", "pre", "w"})
    # Words that describe the kind of answer wanted, not the topic ("speculative decoding definition"). Required in the
    # search they cut the matches to a handful (1 and 4 matches in run 6), so they are left out of the Scopus query.
    SCOPUS_FILLER = frozenset({"definition", "definitions", "overview", "introduction", "intro", "basics", "basic", "concept",
                               "concepts", "explained", "explanation", "meaning", "pros", "cons"})
    SCOPUS_MIN_MATCHES = 10          # below this many matches the relaxed query is searched as well

    def _scopus_queries(self, text: str) -> list[str]:
        """Scopus queries for a natural-language search query: [strict] or [strict, relaxed].

        Strict: the first two content words are required, the rest only widen the match (all-AND returned nothing for 3 of 16
        real planner queries; Scopus sorts by relevance, so the top 25 are the best matches). When just ONE word is left over
        it would become required too (an all-AND query that finds 1 to 4 papers), so a relaxed query without it is added; the
        pipeline searches it only if the strict one finds fewer than SCOPUS_MIN_MATCHES. Articles, conference papers and
        reviews in English."""
        words = [
            w for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9\-]*", text)
            if w.lower() not in self.OPENALEX_STOPWORDS and w.lower() not in self.SCOPUS_RESERVED
            and w.lower() not in self.SCOPUS_FILLER and len(w) > 1
        ]
        words = list(dict.fromkeys(words))
        if not words:
            return []

        suffix = " AND (DOCTYPE(ar) OR DOCTYPE(cp) OR DOCTYPE(re)) AND LANGUAGE(english)"
        if self.scopus_min_year:
            suffix += f" AND PUBYEAR > {self.scopus_min_year - 1}"

        def build(required: list[str], optional: list[str]) -> str:
            query = f"TITLE-ABS-KEY({' AND '.join(required)})"
            if optional:
                query += f" AND TITLE-ABS-KEY({' OR '.join(optional)})"
            return query + suffix

        strict = build(words[:2], words[2:])
        if len(words) == 3:                                    # the third word is required in the strict query
            return [strict, build(words[:2], [])]
        if len(words) == 2:                                    # both required: relax to either word
            return [strict, f"TITLE-ABS-KEY({' OR '.join(words)})" + suffix]
        return [strict]

    def _scopus_query(self, text: str) -> str | None:
        """The strict Scopus query for a search query (see _scopus_queries), or None if it has no content words."""
        queries = self._scopus_queries(text)
        return queries[0] if queries else None

    async def _safe_scopus_search(self, query: str) -> list[PaperResult]:
        if self._scopus_disabled:
            return []
        scopus_queries = self._scopus_queries(query)
        if not scopus_queries:
            return []
        try:
            async with self._scopus_semaphore:
                data = await asyncio.to_thread(trace_llm_service.scopus_search, scopus_queries[0], self.scopus_results)
                if len(scopus_queries) > 1 and data.get("view") == "COMPLETE" and (data.get("total") or 0) < self.SCOPUS_MIN_MATCHES:
                    relaxed = await asyncio.to_thread(trace_llm_service.scopus_search, scopus_queries[1], self.scopus_results)
                    logger.info("Scopus: strict query found %s matches for '%s'; relaxed query found %s",
                                data.get("total"), query[:50], relaxed.get("total"))
                    data = {**data, "entries": data["entries"] + [e for e in relaxed.get("entries", [])
                                                                  if e.get("dc:identifier") not in {x.get("dc:identifier") for x in data["entries"]}],
                            "total": relaxed.get("total", data.get("total"))}
        except trace_llm_service.TraceLLMError as e:
            text = str(e)
            if any(code in text for code in ("HTTP 404", "HTTP 503", "marked unavailable", "rejected the API key")):
                if not self._scopus_disabled:
                    self._scopus_disabled = text[:120]
                    logger.warning("Scopus unavailable, skipping it for this run: %s", text[:160])
            else:
                logger.warning("Scopus search failed for '%s': %s", query[:60], text[:160])
            return []
        except Exception as e:
            logger.warning("Scopus search failed for '%s': %s: %s", query[:60], type(e).__name__, e)
            return []

        if data.get("view") != "COMPLETE":
            if not self._scopus_disabled:
                self._scopus_disabled = "host cannot read abstracts (STANDARD view only)"
                logger.warning("Scopus gave no abstracts (view=%s): skipping it for this run", data.get("view"))
            return []
        papers = self._parse_scopus_results(data["entries"], query)
        logger.info("Scopus: %d papers (of %s matches) for '%s'", len(papers), data.get("total"), query[:60])
        return papers

    @staticmethod
    def _scopus_authors(entry: dict) -> list[str]:
        raw = entry.get("author")
        if isinstance(raw, dict):
            raw = [raw]
        names = []
        for a in raw or []:
            name = a.get("authname") or " ".join(x for x in (a.get("given-name"), a.get("surname")) if x)
            if name:
                names.append(name.strip())
        return names or ([entry["dc:creator"]] if entry.get("dc:creator") else [])

    def _parse_scopus_results(self, entries: list[dict], query: str) -> list[PaperResult]:
        results = []
        for e in entries:
            title = (e.get("dc:title") or "").strip()
            abstract = re.sub(r"\s+", " ", (e.get("dc:description") or "").strip())
            abstract = re.sub(r"^(abstract|summary)\s*[:.\-]?\s*", "", abstract, flags=re.I)
            abstract = re.sub(r"\s*©.*$", "", abstract).strip()          # trailing publisher copyright notice
            if not title or not abstract:
                continue
            date = (e.get("prism:coverDate") or "").strip()
            try:
                year = int(date[:4])
            except ValueError:
                year = None
            try:
                citations = int(e.get("citedby-count"))
            except (TypeError, ValueError):
                citations = None
            doi = (e.get("prism:doi") or "").strip().lower() or None
            results.append(PaperResult(
                title=title,
                abstract=abstract,
                authors=self._scopus_authors(e),
                year=year,
                venue=(e.get("prism:publicationName") or "").strip() or None,
                citation_count=citations,
                influential_citation_count=None,
                is_preprint=False,                      # Scopus indexes peer-reviewed sources
                source="scopus",
                arxiv_id=None,
                doi=doi,
                pdf_url=None,                           # Scopus gives no PDF link; parsing goes through the DOI / Unpaywall path
                published_date=date or None,
                tldr=None,
                fields_of_study=[],
                query_variant_matched=[query],
            ))
        return results

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
