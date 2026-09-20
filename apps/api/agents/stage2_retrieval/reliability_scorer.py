# apps/api/agents/stage2_retrieval/reliability_scorer.py
from datetime import datetime
from typing import Union
import logging

logger = logging.getLogger("apps.api.agents.stage2_retrieval")

TRUSTED_WEB_DOMAINS = [
    ".edu", ".gov", "nature.com", "ieee.org", "acm.org",
    "research.google", "arxiv.org", "aws.amazon.com",
    "ibm.com", "microsoft.com", "openai.com", "anthropic.com",
    "ncbi.nlm.nih.gov", "springer.com", "sciencedirect.com"
]

TOP_VENUES = [
    "neurips", "icml", "acl", "emnlp", "nature", "science",
    "ieee", "cvpr", "iclr", "aaai", "jmlr"
]

CURRENT_YEAR = datetime.now().year


def _safe_year(date_str) -> int | None:
    """Extract a 4-digit year safely; returns None on any failure."""
    if not date_str:
        return None
    try:
        return int(str(date_str)[:4])
    except (ValueError, TypeError):
        return None


def score_web_source(source) -> float:
    """Scores a web Source object. Base 0.3, up to +0.65 from signals."""
    score = 0.3  # conservative base — unknown sources start low

    url = (getattr(source, "url", "") or "").lower()
    if not url:
        return 0.1  # malformed source — lowest band, don't crash

    if any(d in url for d in TRUSTED_WEB_DOMAINS):
        score += 0.30

    year = _safe_year(getattr(source, "published_date", None))
    if year is not None:
        age = CURRENT_YEAR - year
        if age <= 1:
            score += 0.20
        elif age <= 3:
            score += 0.10
    # else: no penalty, just no bonus — most pages lack this field

    snippet = getattr(source, "snippet", "") or ""
    if len(snippet) > 200:
        score += 0.10

    provider = (getattr(source, "provider", "") or "").lower()
    if provider in ("tavily", "exa"):
        score += 0.05

    return round(min(score, 1.0), 2)


def score_paper(paper: dict) -> float:
    """Scores a paper dict (from arXiv/Semantic Scholar). Base 0.25, up to +0.85 from signals."""
    score = 0.25  # conservative base

    if not paper.get("is_preprint", True) and paper.get("venue"):
        score += 0.25
        if any(v in paper["venue"].lower() for v in TOP_VENUES):
            score += 0.15

    citations = paper.get("citation_count") or 0
    if citations >= 50:
        score += 0.20
    elif citations >= 10:
        score += 0.12
    elif citations >= 1:
        score += 0.05

    influential = paper.get("influential_citation_count") or 0
    if influential >= 5:
        score += 0.10
    elif influential >= 1:
        score += 0.05

    year = _safe_year(paper.get("published_date"))
    if year is not None:
        age = CURRENT_YEAR - year
        if age <= 1:
            score += 0.10
        elif age <= 3:
            score += 0.05

    return round(min(score, 1.0), 2)


def score_source(source: Union[object, dict]) -> float:
    """Single entry point — routes to the right scorer based on type (dict=paper, object=web Source)."""
    try:
        if isinstance(source, dict):
            return score_paper(source)
        return score_web_source(source)
    except Exception as e:
        logger.error("Scoring failed, defaulting to 0.3: %s", e)
        return 0.3  # never let a scoring bug break the pipeline


def score_all(sources: list) -> list:
    """Scores a mixed list of web Sources and/or paper dicts in place."""
    for s in sources:
        if isinstance(s, dict):
            s["reliability_score"] = score_paper(s)
        else:
            s.reliability_score = score_web_source(s)
        logger.info("Scored source: %.2f", s["reliability_score"] if isinstance(s, dict) else s.reliability_score)
    return sources