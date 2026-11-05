import html
import re

from rapidfuzz import fuzz

MIN_PIECE_CHARS = 20            # a quote (or a piece of one) shorter than this is never accepted: too easy to match by chance

_CITATION = re.compile(r"\[\s*\d+(?:\s*[,\u2013\u2014-]\s*\d+)*\s*\]")    # [4]  [28, 4]  [5-7]
_ELLIPSIS = re.compile(r"\[\s*(?:\.{3}|\u2026)\s*\]|\.{3}|\u2026")        # [...]  ...  the single character


def _norm(t: str) -> str:
    """Lower-case, whitespace-collapsed text without what extraction and the digest model change but not the meaning of a passage:
    hyphenation and soft hyphens, HTML entities (&lt;), citation markers ([4], [28, 4]), typographic hyphens, and the spaces Docling puts
    inside parentheses ("( K = 1 )"). Used on both the quote and the chunk, so it only makes matching more tolerant of those."""
    t = html.unescape(t or "")
    t = t.replace("-\n", "").replace("\u00ad", "")
    t = re.sub(r"[\u2010\u2011\u2012\u2013]", "-", t)
    t = _CITATION.sub(" ", t)
    t = re.sub(r"\(\s+", "(", t)
    t = re.sub(r"\s+\)", ")", t)
    return re.sub(r"\s+", " ", t.lower()).strip()


def _found(piece: str, chunks: list[str], fuzzy_threshold: int) -> bool:
    return any(piece in c or fuzz.partial_ratio(piece, c) >= fuzzy_threshold for c in chunks)


def verify_quote(quote: str, chunk_texts: list[str], fuzzy_threshold: int = 92) -> bool:
    """True if the quote appears in at least one chunk (exact, or near-exact to tolerate PDF hyphenation/spacing noise).

    A quote with an elision ("... ", "[...]") is split at it and accepted when every piece of at least MIN_PIECE_CHARS is found in a chunk
    (each piece is real text; the digest model joined them). A quote that joins pieces without marking it, or paraphrases, still fails."""
    chunks = [_norm(c) for c in chunk_texts]
    pieces = [_norm(p) for p in _ELLIPSIS.split(quote or "")]
    pieces = [p for p in pieces if len(p) >= MIN_PIECE_CHARS]
    if not pieces:
        return False
    return all(_found(p, chunks, fuzzy_threshold) for p in pieces)
