# apps/api/agents/stage2_retrieval/markdown_parser.py
"""Structure extraction from the Markdown that Docling produces for a paper.

Pure functions (no I/O) so they can be tested on stored full_text. Docling's Markdown is inconsistent: titles, author
lines, running page headers and figure labels all come out as headings, the abstract may be a heading, an inline
"Abstract - ..." paragraph or unlabeled, and references may be bulleted, numbered or plain lines. The rules below are
deliberately defensive. The caller should prefer API metadata (title/authors/abstract) and use this only as a fallback;
the sections, the references and the abstract fallback are what it is really for.
"""
import html
import re
from dataclasses import dataclass, field

# Bump whenever the parsing rules change in a way that makes stored rows worse than a fresh parse: only parsed_papers
# rows with parser_version >= this are reused by the parse cache.
PARSER_VERSION = 1

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
NUMBERING_RE = re.compile(r"^(?:(\d+(?:\.\d+)*)\.?|([IVXLC]+)\.|([A-Z])\.)\s+\S")

KNOWN_SECTION_RE = re.compile(
    r"^(?:\d+(?:\.\d+)*\.?\s+|[IVXLC]+\.\s+)?(abstract|introduction|background|related work|related works|"
    r"preliminar(?:y|ies)|overview|methods?|methodology|approach|experiments?|experimental (?:setup|results)|"
    r"results?|discussion|evaluation|analysis|limitations?|future (?:work|directions?)|conclusions?|"
    r"acknowledg(?:e)?ments?|appendix|appendices|references|bibliography)\b",
    re.I,
)
REFERENCES_RE = re.compile(
    r"^\W*(?:(?:\d+|[IVXLC]+)[\.\)]?\s+)?(?:references?(?: list)?|bibliography|works cited|literature cited)\W*$", re.I)
POST_REFERENCES_RE = re.compile(r"^\W*(?:(?:\d+|[A-Z])[\.\)]?\s+)?(?:appendix|appendices|supplementary)", re.I)
ABSTRACT_LABEL_RE = re.compile(r"^\W*(abstract|summary)\b[\s.:\-–—−]*(.*)$", re.I)
BOILERPLATE_HEADING_RE = re.compile(r"^\W*(acm ?reference format|ccs concepts|additional key words)", re.I)
KEYWORDS_RE = re.compile(r"^\W*(keywords?|index terms|key words|ccs concepts|categories and subject)\b", re.I)

AFFILIATION_RE = re.compile(
    r"\b(universit|institut|department|dept\.|laborator|\blab\b|school of|college|faculty|corporation|"
    r"company|academy|centre|center for|e-?mail|@|\.edu|\.org|\.com)", re.I)
JOURNAL_RE = re.compile(
    r"\b(journal|proceedings|transactions|conference|issn|e-issn|p-issn|vol\.|volume|pp\.|doi|arxiv|preprint|"
    r"copyright|licen[sc]e|received|accepted|published|homepage|abbreviated key title)\b", re.I)
FIGURE_LABEL_RE = re.compile(r"^(caption|figure|fig\.|table|algorithm|video content|image content|listing)\s*\d*\b", re.I)
AUTHOR_MARKS_RE = re.compile(r"[*∗†‡§¶#♠♡♢♣⋆☼♦\d]+")

MAX_HEADING_CHARS = 120
MAX_AUTHORS = 40
MIN_SECTION_CHARS = 60      # an unnumbered "section" with less text than this is a figure label or a stray line


@dataclass
class ParsedMarkdown:
    title: str = ""
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    sections: list[dict] = field(default_factory=list)      # {"heading", "text", "level"}
    references: list[str] = field(default_factory=list)


def clean_text(text: str) -> str:
    """Unescape entities, drop image/comment markers and collapse the runs of spaces that PDF extraction leaves."""
    text = html.unescape(text or "")
    text = re.sub(r"<!--.*?-->", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_abstract(text: str) -> str:
    text = clean_text(text)
    text = re.sub(r"^(?:review|research|original|short|regular) (?:article|paper)\s+", "", text, flags=re.I)
    return text.lstrip("-–—−:. ").strip()


def _looks_like_names(text: str) -> bool:
    """'Jiafeng Gu *', 'Naveen Lamba 1* , Sanju Tiwari 1 and Manas Gaur', 'Hwiyoon Kim' - a list of person names."""
    stripped = AUTHOR_MARKS_RE.sub(" ", clean_text(text))
    stripped = re.sub(r"\band\b|&", ",", stripped)
    parts = [p.strip() for p in stripped.split(",") if p.strip()]
    if not parts or len(parts) > 15:
        return False
    min_tokens = 1 if len(parts) >= 2 and any(len(p.split()) >= 2 for p in parts) else 2   # 'A B Rathod, Anurag'
    for p in parts:
        tokens = [t for t in re.split(r"[\s]+", p) if t]
        if not min_tokens <= len(tokens) <= 5:
            return False
        if not all(re.match(r"^(?:[A-Z][\w'\-\.]*|van|von|de|der|da|di|del|bin|al|le|la)$", t) for t in tokens):
            return False
    return True


def _is_section_heading(text: str, in_front_matter: bool, seen_headings: dict[str, int]) -> bool:
    """False for author lines, affiliations, running page headers and figure labels that Docling emits as headings."""
    h = clean_text(text)
    if not h or len(h) > MAX_HEADING_CHARS:
        return False
    if NUMBERING_RE.match(h) or KNOWN_SECTION_RE.match(h):
        return True
    if h[0].islower():                                  # a sentence fragment, 'where:'
        return False
    if FIGURE_LABEL_RE.match(h) or AFFILIATION_RE.search(h) or JOURNAL_RE.search(h):
        return False
    if seen_headings.get(h.lower(), 0) >= 1:            # the same unnumbered heading repeated = running header
        return False
    if in_front_matter and _looks_like_names(h):
        return False
    return True


def _heading_level(text: str, hashes: int) -> int:
    m = NUMBERING_RE.match(clean_text(text))
    if m and m.group(1):
        return min(m.group(1).count(".") + 1, 4)
    return 1 if hashes <= 2 else min(hashes - 1, 4)


def parse_markdown(md: str) -> ParsedMarkdown:
    lines = md.split("\n")
    out = ParsedMarkdown()

    # pass 1: classify lines into front matter / sections / references
    seen_headings: dict[str, int] = {}
    front: list[str] = []                               # lines before the first real section heading
    in_front = True
    in_refs = False
    current: dict | None = None
    abstract_heading_lines: list[str] = []
    in_abstract_heading = False
    ref_lines: list[str] = []
    title_set = False

    for raw in lines:
        line = raw.strip()
        m = HEADING_RE.match(line)
        if m:
            hashes, heading_text = len(m.group(1)), clean_text(m.group(2))
            if not title_set and not JOURNAL_RE.search(heading_text) and not FIGURE_LABEL_RE.match(heading_text) \
                    and not KNOWN_SECTION_RE.match(heading_text) and not heading_text.lower().startswith(("acm reference", "acmreference")):
                out.title = heading_text
                title_set = True
                front.append(line)
                continue

            if REFERENCES_RE.match(heading_text):
                in_refs, current, in_abstract_heading, in_front = True, None, False, False
                continue
            if in_refs and POST_REFERENCES_RE.match(heading_text):
                in_refs = False
            if re.match(r"^\W*abstract\W*$", heading_text, re.I):
                in_abstract_heading, in_refs = True, False
                continue
            if in_refs:
                continue                                # headings inside the reference list are noise
            if not BOILERPLATE_HEADING_RE.match(heading_text) and \
                    _is_section_heading(heading_text, in_front, seen_headings):
                seen_headings[heading_text.lower()] = seen_headings.get(heading_text.lower(), 0) + 1
                in_abstract_heading = False
                in_front = False
                current = {"heading": heading_text, "text": "", "level": _heading_level(heading_text, hashes)}
                out.sections.append(current)
                continue
            line = heading_text             # not a real section heading: keep it as ordinary text

        if not line:
            continue
        if REFERENCES_RE.match(clean_text(line)) and len(line) < 40:     # 'References' as a plain line
            in_refs, current, in_abstract_heading, in_front = True, None, False, False
            continue
        if in_refs:
            ref_lines.append(line)
        elif in_abstract_heading:
            abstract_heading_lines.append(line)
        elif current is not None:
            current["text"] += line + "\n"
        else:
            front.append(line)

    # abstract
    abstract = ""
    if abstract_heading_lines:
        kept = []
        for l in abstract_heading_lines:
            if KEYWORDS_RE.match(l):
                break
            kept.append(l)
        abstract = " ".join(kept)
    if not abstract:
        for i, l in enumerate(front):
            m = ABSTRACT_LABEL_RE.match(l)
            if m:
                parts = [m.group(2)] if m.group(2) else []
                for nxt in front[i + 1:]:
                    if KEYWORDS_RE.match(nxt) or HEADING_RE.match(nxt) or (parts and len(" ".join(parts)) > 400 and len(nxt) < 60):
                        break
                    parts.append(nxt)
                    if len(" ".join(parts)) > 6000:
                        break
                    if m.group(2):
                        break                           # inline abstract is a single paragraph
                abstract = " ".join(parts)
                break
    if not abstract:                                    # unlabeled: the first long paragraph of prose in the front matter
        for l in front:
            if HEADING_RE.match(l) or KEYWORDS_RE.match(l) or AFFILIATION_RE.search(l[:200]) and len(l) < 300:
                continue
            if len(l) >= 400:
                abstract = l
                break
    out.abstract = clean_abstract(abstract)

    # authors (fallback only): short name-like lines between the title and the abstract / first section
    authors: list[str] = []
    started = False
    for l in front:
        h = HEADING_RE.match(l)
        text = clean_text(h.group(2) if h else l)
        if not started:
            started = bool(h) and text == out.title
            continue
        if ABSTRACT_LABEL_RE.match(text) or KEYWORDS_RE.match(text) or len(text) > 200:
            break
        if "@" in text or AFFILIATION_RE.search(text) or JOURNAL_RE.search(text):
            continue
        if _looks_like_names(text):
            for part in re.split(r",|\band\b|&", AUTHOR_MARKS_RE.sub(" ", text)):
                name = re.sub(r"\s+", " ", part).strip(" .*")
                if name and name not in authors:
                    authors.append(name)
    out.authors = authors[:MAX_AUTHORS]

    # references: one entry per non-trivial line
    refs = []
    for l in ref_lines:
        entry = re.sub(r"^(?:[-*•]\s*)", "", l).strip()
        if len(entry) >= 25 and not re.match(r"^\d+$", entry):
            refs.append(clean_text(entry))
    out.references = refs[:1000]

    # fold name-like or tiny unnumbered "sections" (figure labels, stray author lines) into the previous section
    merged: list[dict] = []
    for sec in out.sections:
        numbered = bool(NUMBERING_RE.match(sec["heading"]) or KNOWN_SECTION_RE.match(sec["heading"]))
        text_len = len(sec["text"].strip())
        stray = (not numbered and merged
                 and (text_len < MIN_SECTION_CHARS or (_looks_like_names(sec["heading"]) and text_len < 300)))
        if stray:
            merged[-1]["text"] += sec["heading"] + "\n" + sec["text"]
        else:
            merged.append(sec)
    out.sections = merged
    for sec in out.sections:
        sec["text"] = sec["text"].rstrip("\n")
    return out
