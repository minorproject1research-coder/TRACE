# apps/api/agents/stage3_summarizer/quote_verifier.py
import re
from rapidfuzz import fuzz


def _norm(t: str) -> str:
    t = t.replace("-\n", "").replace("\u00ad", "")
    return re.sub(r"\s+", " ", t.lower()).strip()


def verify_quote(quote: str, chunk_texts: list[str], fuzzy_threshold: int = 92) -> bool:
    """True if the quote appears in at least one chunk (exact, or near-exact
    to tolerate PDF hyphenation/spacing noise)."""
    q = _norm(quote or "")
    if len(q) < 20:
        return False
    for c in map(_norm, chunk_texts):
        if q in c or fuzz.partial_ratio(q, c) >= fuzzy_threshold:
            return True
    return False