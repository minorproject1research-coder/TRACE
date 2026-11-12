"""The reference list of the written report: one entry per DOCUMENT, numbered in the order the report first cites it. Pure Python, no I/O.

Python builds every citation; the language model never writes a [n], an author, a year or a URL. The book is fed the `sources` dict of the
loader ({source_id: metadata}) and the evidence entries of the claims that a sentence uses; it answers with the numbers to print.

  - Identity of a document = Stage 4's `doc_key` (normalised title). The same paper found under two sub-questions (two source ids) and the
    same document found as a paper and as a web page are ONE reference; the reference keeps all their source ids.
  - Metadata may be missing (no authors, no year, no venue, a web page without a date): the entry is built from what exists and never fails.
  - Papers: authors, year, venue, DOI, url (the url rule is paper_service's `_paper_url`, not a third copy).
    Web: title, domain taken from the url, published date as written, url.
  - `accessed` is a date (YYYY-MM-DD) taken from the run's created_at; it is printed for web references only.
"""
import re
from datetime import datetime
from typing import Iterable, Optional
from urllib.parse import urlparse

from apps.api.agents.stage4_factcheck.common import doc_key
from apps.api.agents.stage5_report.schema import Claim, Evidence, Reference

LEVEL_RANK = {"full_text": 3, "abstract": 2, "web_snippet": 1}
CITED_RELATIONS = ("supports", "near_match")        # the evidence a sentence about a claim cites (the other side of a disagreement is cited by cite_evidence)
MAX_AUTHORS_SHOWN = 3
UNTITLED = "Untitled source"


# ---------------------------------------------------------------------------------------------------------------------- small helpers
def ref_key_of(title: Optional[str], source_id="") -> str:
    """The identity of a document: Stage 4's doc_key (the title without a site suffix, lower case, letters and digits only)."""
    return doc_key(title, source_id)


def domain_of(url: Optional[str]) -> Optional[str]:
    """The site of a web url ("https://www.Example.com/a" -> "example.com"); None when the url is missing or has no host."""
    if not url or not isinstance(url, str):
        return None
    try:
        host = urlparse(url.strip() if "://" in url else "//" + url.strip()).hostname
    except ValueError:
        return None
    if not host:
        return None
    host = host.lower()
    return host[4:] if host.startswith("www.") else host


def accessed_date(created_at) -> str:
    """YYYY-MM-DD from the run's created_at (an ISO string or a datetime); "" when it cannot be read."""
    if isinstance(created_at, datetime):
        return created_at.date().isoformat()
    m = re.match(r"\s*(\d{4}-\d{2}-\d{2})", str(created_at or ""))
    return m.group(1) if m else ""


def _year(value, published: Optional[str] = None) -> Optional[int]:
    """The year as an int. A year given as text is converted; a missing year is read from the published date when that has one."""
    for v in (value, published):
        m = re.search(r"\b(1[89]\d{2}|20\d{2})\b", str(v)) if v not in (None, "") else None
        if m:
            return int(m.group(1))
    return None


def _clean(value) -> Optional[str]:
    s = re.sub(r"\s+", " ", str(value)).strip() if value not in (None, "") else ""
    return s or None


def _authors(value) -> list:
    """A list of author names as text (the database stores a list of strings; a JSON string, dicts or a single string are tolerated)."""
    if isinstance(value, str):
        value = [value]
    out = []
    for a in value if isinstance(value, (list, tuple)) else []:
        name = a.get("name") or a.get("display_name") if isinstance(a, dict) else a
        name = _clean(name)
        if name:
            out.append(name)
    return out


def _paper_url(p: dict) -> Optional[str]:
    from apps.api.services.paper_service import _paper_url as paper_url      # imported late: paper_service pulls in the parser stack
    return paper_url(p)


def _richness(meta: dict) -> int:
    return sum(1 for k in ("authors", "year", "venue", "doi") if meta.get(k))


def render_marker(numbers: Iterable[int]) -> str:
    """[1, 3] for the reference numbers of a sentence (sorted, each once); "" when there are none."""
    nums = sorted({int(n) for n in numbers or []})
    return "[" + ", ".join(str(n) for n in nums) + "]" if nums else ""


def _join_authors(authors: list) -> str:
    if len(authors) <= 1:
        return "".join(authors)
    if len(authors) <= MAX_AUTHORS_SHOWN:
        return ", ".join(authors[:-1]) + " and " + authors[-1]
    return ", ".join(authors[:MAX_AUTHORS_SHOWN]) + " et al."


def format_reference(ref: Reference, *, markdown: bool = False, accessed: str = "") -> str:
    """One reference as a line of text (without its number). Papers: "A, B and C (2021). Title. Venue. DOI/URL". Web: "Title. site, published. URL
    (accessed date)". Missing parts are left out; a missing year of a paper is written "n.d.". Markdown italicises the title and links the url."""
    title = ref.title or UNTITLED
    title_txt = f"*{title}*" if markdown else title
    url = ref.url or ""
    url_txt = f"[{url}]({url})" if markdown and url else url
    if ref.kind == "paper":
        head = _join_authors(ref.authors or [])
        year = f"({ref.year})" if ref.year else "(n.d.)"
        parts = [f"{head} {year}." if head else f"{year}.", f"{title_txt}."]
        if ref.venue:
            parts.append(f"{ref.venue}.")
        if url_txt:
            parts.append(url_txt)
        return " ".join(parts)
    where = ", ".join(x for x in (ref.domain, ref.published) if x)
    parts = [f"{title_txt}."]
    if where:
        parts.append(f"{where}.")
    if url_txt:
        parts.append(url_txt)
    if accessed:
        parts.append(f"(accessed {accessed})")
    return " ".join(parts)


# ----------------------------------------------------------------------------------------------------------------------- the book
class ReferenceBook:
    """Registers documents in order of first citation and hands out numbers.

    book = ReferenceBook(inputs["sources"], accessed=accessed_date(inputs["created_at"]))
    numbers = book.cite(sentence_claims)         # [2, 5]; a document cited for the first time gets the next free number
    book.render_marker(numbers)                  # "[2, 5]"
    book.references()                            # list[Reference] in numbered order, for the reference list
    """

    def __init__(self, sources: Optional[dict] = None, *, accessed: str = ""):
        self.accessed = accessed or ""
        self._by_key: dict[str, list] = {}              # ref_key -> [(source_id, meta)] from the sources dict
        for sid, meta in sorted((sources or {}).items(), key=lambda kv: str(kv[0])):
            meta = meta if isinstance(meta, dict) else {}
            self._by_key.setdefault(ref_key_of(meta.get("title"), sid), []).append((str(sid), meta))
        self._refs: dict[str, Reference] = {}           # ref_key -> Reference, in order of first citation
        self._best_level: dict[str, Optional[str]] = {}

    # ---- registering
    def cite_key(self, ref_key: str, *, title: str = "", source_id: str = "", level: Optional[str] = None) -> int:
        """The number of the document `ref_key`, registering it on first use. `title` / `source_id` are used when the sources dict does not know it."""
        ref = self._refs.get(ref_key)
        if ref is None:
            ref = self._build(len(self._refs) + 1, ref_key, title, source_id)
            self._refs[ref_key] = ref
            self._best_level[ref_key] = None
        if source_id and str(source_id) not in ref.source_ids:
            ref.source_ids.append(str(source_id))
            ref.source_ids.sort()
        if level in LEVEL_RANK and LEVEL_RANK[level] > LEVEL_RANK.get(self._best_level[ref_key], 0):
            self._best_level[ref_key] = level
            ref.evidence_level = level
        return ref.number

    def cite_evidence(self, ev: Evidence) -> int:
        key = ev.ref_key or ref_key_of(ev.title, ev.source_id)
        return self.cite_key(key, title=ev.title or "", source_id=ev.source_id or "", level=ev.evidence_level)

    def cite(self, items, *, relations=CITED_RELATIONS) -> list:
        """Reference numbers (sorted, each once) for a Claim, an Evidence entry or a list of them. For a Claim, the evidence of the given relations is cited:
        the supporting quotes and, for a partly supported claim, the near-match quote of the second document (never the conflicting side)."""
        if isinstance(items, (Claim, Evidence)):
            items = [items]
        numbers = set()
        for it in items or []:
            if isinstance(it, Evidence):
                numbers.add(self.cite_evidence(it))
            elif isinstance(it, Claim):
                numbers.update(self.cite_evidence(e) for e in it.evidence if e.relation in relations)
        return sorted(numbers)

    @staticmethod
    def render_marker(numbers: Iterable[int]) -> str:
        return render_marker(numbers)

    # ---- reading
    def references(self) -> list:
        return sorted(self._refs.values(), key=lambda r: r.number)

    def get(self, number: int) -> Optional[Reference]:
        return next((r for r in self._refs.values() if r.number == number), None)

    def format_reference(self, ref: Reference, *, markdown: bool = False) -> str:
        return format_reference(ref, markdown=markdown, accessed=self.accessed if ref.kind == "web" else "")

    # ---- building one Reference
    def _build(self, number: int, ref_key: str, title: str, source_id: str) -> Reference:
        known = list(self._by_key.get(ref_key, []))
        ids = sorted({sid for sid, _ in known} | ({str(source_id)} if source_id else set()))
        papers = sorted([m for _, m in known if m.get("kind") == "paper"], key=lambda m: (-_richness(m), str(m.get("title") or "")))
        webs = [m for _, m in known if m.get("kind") != "paper"]
        primary = (papers or webs or [{}])[0]
        merged = {k: next((m.get(k) for m in papers + webs if m.get(k) not in (None, "", [])), None)
                  for k in ("authors", "year", "venue", "doi", "arxiv_id", "pdf_url", "url", "provider", "published")}
        kind = "paper" if papers else "web"
        title = _clean(primary.get("title")) or _clean(title) or UNTITLED
        if kind == "paper":
            url = _clean(merged["url"]) or _clean(_paper_url(merged))      # the loader already stored the url made by paper_service's rule
            levels = [m.get("evidence_level") for m in papers]
            return Reference(number=number, ref_key=ref_key, kind="paper", title=title, authors=_authors(merged["authors"]),
                             year=_year(merged["year"], merged["published"]), venue=_clean(merged["venue"]), doi=_clean(merged["doi"]),
                             url=url, source_ids=ids, evidence_level=max(levels, key=lambda l: LEVEL_RANK.get(l, 0), default=None),
                             published=_clean(merged["published"]), domain=None)
        url = _clean(merged["url"])
        return Reference(number=number, ref_key=ref_key, kind="web", title=title, authors=[], year=None, venue=None, doi=None, url=url,
                         source_ids=ids, evidence_level="web_snippet" if webs else None, published=_clean(merged["published"]), domain=domain_of(url))
