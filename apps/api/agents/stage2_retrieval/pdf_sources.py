# apps/api/agents/stage2_retrieval/pdf_sources.py
"""Legitimate routes to a paper's PDF when its own link does not deliver one.

Publishers such as ACM, MDPI and IEEE block scripted downloads (HTTP 403 "bot protection") and some forbid them in their terms, so this
module does NOT try to defeat that protection. It uses routes that are meant for programs:

  * the OpenAlex Content API  - OpenAlex's own cached copy of about 50 million open-access PDFs (official, a free key works)
  * the OSF and Zenodo APIs   - the repositories' official file endpoints
  * the arXiv API             - the same paper as an arXiv preprint, matched by exact title

plus the polite-access rules every request follows (honest User-Agent, spacing per host, robots.txt for pages we only follow).
Every route is switched by an environment variable and returns the PDF bytes or None; a file counts as a PDF only if it starts with
"%PDF-" and has at least MIN_PDF_BYTES bytes. Report: docs/reports/06_pdf_access_plan.md.
"""
import asyncio
import difflib
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from typing import Optional
from urllib.parse import quote, urlparse
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger("apps.api.agents.stage2_retrieval.pdf_sources")


def env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() not in ("0", "false", "no", "off")


# Each switch: true = on, false = off.
OPENALEX_CONTENT = env_flag("OPENALEX_CONTENT", True)          # OpenAlex Content API (cached open-access PDFs)
REPOSITORY_APIS = env_flag("REPOSITORY_APIS", True)            # OSF and Zenodo file APIs
ARXIV_TITLE_TWIN = env_flag("ARXIV_TITLE_TWIN", True)          # the same paper as an arXiv preprint (exact title)
HTML_FULLTEXT = env_flag("HTML_FULLTEXT", True)                # full article inside an HTML page, read by Docling
HTML_FULLTEXT_MIN_CHARS = int(os.getenv("HTML_FULLTEXT_MIN_CHARS", "15000"))   # abstract pages are 5,000 to 8,000 characters
RESPECT_ROBOTS_TXT = env_flag("RESPECT_ROBOTS_TXT", True)      # for landing pages whose PDF link we follow
POLITE_HOST_INTERVAL_SECONDS = float(os.getenv("POLITE_HOST_INTERVAL_SECONDS", "2.0"))   # min gap between requests to one host; 0 = off

MIN_PDF_BYTES = 10_000
OPENALEX_WORKS_URL = "https://api.openalex.org/works"
OPENALEX_CONTENT_URL = "https://content.openalex.org/works"


class PdfTooLargeError(Exception):
    """The PDF is over MAX_PDF_SIZE_MB; no other source is tried because it would be the same file."""


class PolitePolicy:
    """Spacing between requests to the same host, and robots.txt."""

    def __init__(self, user_agent: str, interval: float = POLITE_HOST_INTERVAL_SECONDS):
        self.user_agent = user_agent
        self.interval = interval
        self._next_slot: dict[str, float] = {}
        self._robots: dict[str, Optional[RobotFileParser]] = {}
        self._lock = asyncio.Lock()

    async def wait(self, url: str) -> None:
        """Sleep until this host may be asked again (at least `interval` seconds after the previous request to it)."""
        if self.interval <= 0:
            return
        host = urlparse(url).netloc.lower()
        async with self._lock:
            now = time.monotonic()
            slot = max(self._next_slot.get(host, 0.0), now)
            self._next_slot[host] = slot + self.interval
        if slot > now:
            await asyncio.sleep(slot - now)

    async def robots_allows(self, client: httpx.AsyncClient, url: str) -> bool:
        """False only if the host's robots.txt disallows this URL for us. An unreachable or missing robots.txt allows it."""
        parts = urlparse(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self._robots:
            parser = None
            try:
                r = await client.get(f"{host}/robots.txt", headers={"User-Agent": self.user_agent}, timeout=10, follow_redirects=True)
                if r.status_code == 200 and "html" not in r.headers.get("content-type", "").lower():
                    parser = RobotFileParser()
                    parser.parse(r.text.splitlines())
            except Exception:
                parser = None
            self._robots[host] = parser
        parser = self._robots[host]
        return True if parser is None else parser.can_fetch(self.user_agent, url)


class PdfSources:
    def __init__(self, user_agent: str, polite: PolitePolicy, openalex_pool, arxiv_wait, max_pdf_bytes: int):
        self.user_agent = user_agent
        self.polite = polite
        self.pool = openalex_pool            # KeyPool of OpenAlex keys, or None
        self.arxiv_wait = arxiv_wait         # coroutine function: waits for the arXiv API rate limit
        self.max_pdf_bytes = max_pdf_bytes   # 0 = no cap

    # ------------------------------------------------------------------ helpers
    async def _get(self, client: httpx.AsyncClient, url: str, params=None, headers=None, timeout: float = 30):
        await self.polite.wait(url)
        h = {"User-Agent": self.user_agent}
        h.update(headers or {})
        return await client.get(url, params=params, headers=h, timeout=timeout, follow_redirects=True)

    async def _get_pdf(self, client: httpx.AsyncClient, url: str, headers=None) -> tuple[Optional[bytes], int]:
        """(bytes, status). bytes is None unless the response really is a PDF of a sensible size."""
        await self.polite.wait(url)
        h = {"User-Agent": self.user_agent, "Accept": "application/pdf,*/*;q=0.8"}
        h.update(headers or {})
        chunks, size = [], 0
        async with client.stream("GET", url, headers=h, timeout=120, follow_redirects=True) as resp:
            if resp.status_code != 200:
                return None, resp.status_code
            async for chunk in resp.aiter_bytes():
                if not chunks and chunk.lstrip()[:5] != b"%PDF-":
                    return None, resp.status_code
                size += len(chunk)
                if self.max_pdf_bytes and size > self.max_pdf_bytes:
                    raise PdfTooLargeError(f"over the {self.max_pdf_bytes // 1048576} MB cap (download stopped at {size / 1048576:.1f} MB)")
                chunks.append(chunk)
            status = resp.status_code
        body = b"".join(chunks)
        return (body if len(body) >= MIN_PDF_BYTES else None), status

    @staticmethod
    def _oa_headers(key: str) -> dict:
        return {"Authorization": f"Bearer {key}"}      # in a header, never in the URL, so the key cannot end up in a log line

    # ------------------------------------------------------------------ OpenAlex Content API
    async def openalex_content(self, client: httpx.AsyncClient, meta: dict) -> Optional[bytes]:
        """OpenAlex's cached copy of an open-access PDF. Looks the work up by DOI (the `has_content.pdf` flag), downloads it only if
        OpenAlex has it, and rotates to the next key when one answers 402 / 403 / 429 (spent or rate limited)."""
        doi = (meta.get("doi") or "").strip().lower()
        if not OPENALEX_CONTENT or self.pool is None or not doi:
            return None

        work_id = None
        for _ in range(len(self.pool) + 1):
            key = self.pool.get_key()
            if key is None:
                return None
            r = await self._get(client, OPENALEX_WORKS_URL, params={"filter": f"doi:https://doi.org/{doi}", "select": "id,has_content", "per_page": 1},
                                headers=self._oa_headers(key))
            if r.status_code in (402, 403, 429):
                self.pool.mark_rate_limited(key, 60 if r.status_code == 429 else 3600)
                continue
            if r.status_code != 200:
                return None
            results = r.json().get("results") or []
            if not results or not (results[0].get("has_content") or {}).get("pdf"):
                return None                                  # OpenAlex has no cached PDF for this work
            work_id = results[0]["id"].rsplit("/", 1)[-1]
            break
        if not work_id:
            return None

        for _ in range(len(self.pool) + 1):
            key = self.pool.get_key()
            if key is None:
                return None
            body, status = await self._get_pdf(client, f"{OPENALEX_CONTENT_URL}/{work_id}.pdf", headers=self._oa_headers(key))
            if status in (402, 403, 429):
                self.pool.mark_rate_limited(key, 60 if status == 429 else 3600)
                logger.warning("OpenAlex content key ...%s answered %d; trying the next key", key[-4:], status)
                continue
            return body
        return None

    # ------------------------------------------------------------------ repositories with official file APIs
    async def repository(self, client: httpx.AsyncClient, meta: dict) -> Optional[bytes]:
        """OSF preprints (DOI 10.31219/osf.io/<id>) and Zenodo records (DOI 10.5281/zenodo.<id>) through their documented APIs."""
        doi = (meta.get("doi") or "").strip().lower()
        if not REPOSITORY_APIS or not doi:
            return None
        if doi.startswith("10.31219/osf.io/"):
            guid = doi.split("osf.io/", 1)[1]
            r = await self._get(client, f"https://api.osf.io/v2/preprints/{guid}/")
            if r.status_code != 200:
                return None
            file_api = r.json()["data"]["relationships"]["primary_file"]["links"]["related"]["href"]
            f = await self._get(client, file_api)
            if f.status_code != 200:
                return None
            body, _ = await self._get_pdf(client, f.json()["data"]["links"]["download"])
            return body
        if doi.startswith("10.5281/zenodo."):
            record = doi.split("zenodo.", 1)[1]
            r = await self._get(client, f"https://zenodo.org/api/records/{record}")
            if r.status_code != 200:
                return None
            for entry in r.json().get("files") or []:
                if str(entry.get("key", "")).lower().endswith(".pdf"):
                    body, _ = await self._get_pdf(client, entry["links"]["self"])
                    return body
        return None

    # ------------------------------------------------------------------ the same paper on arXiv
    async def arxiv_twin(self, client: httpx.AsyncClient, meta: dict) -> Optional[bytes]:
        """A publisher paper often also exists as an arXiv preprint. Exact (near-exact) title match only, so a different paper is never fetched."""
        title = (meta.get("title") or "").strip()
        if not ARXIV_TITLE_TWIN or meta.get("arxiv_id") or len(title) < 20:
            return None
        norm = lambda t: re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()
        await self.arxiv_wait()
        query = quote(f'ti:"{re.sub(r"[^A-Za-z0-9 ]", " ", title)[:150]}"')
        r = await self._get(client, f"https://export.arxiv.org/api/query?search_query={query}&max_results=3")
        if r.status_code != 200:
            return None
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for entry in ET.fromstring(r.text).findall("a:entry", ns):
            found = entry.find("a:title", ns).text or ""
            if difflib.SequenceMatcher(None, norm(found), norm(title)).ratio() >= 0.97:
                arxiv_id = re.sub(r"v\d+$", "", entry.find("a:id", ns).text.rsplit("/abs/", 1)[-1])
                logger.info("Found '%s' on arXiv as %s", title[:60], arxiv_id)
                body, _ = await self._get_pdf(client, f"https://arxiv.org/pdf/{arxiv_id}")
                return body
        return None
