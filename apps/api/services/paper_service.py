"""Read-only views of the papers and web sources a run retrieved, for the frontend's Activity tab and paper page. No LLM call, no writes.

  build_papers_overview(query_id)           the funnel (kept, parsed, used as evidence) and one summary row per paper and per web source
  build_paper_detail(query_id, paper_id)    one paper: metadata and links, scores, abstract, the parsed content (markdown from the parser), its
                                            outline, figures and references, and the findings taken from it with the place of each quote in the text

Where a finding's quote sits in the parsed text is found with the same normalization Stage 3 uses to verify quotes (quote_verifier._norm:
hyphenation, citation markers, typographic hyphens, whitespace), so a highlight is shown exactly when the verifier could have found the quote.
When it cannot be placed, no span is returned: a missing highlight is better than a misleading one.

Offsets are in UTF-16 code units, i.e. JavaScript string indexes, because the text is rendered by a browser.
"""
import logging
import re
import uuid
from typing import Any, Optional

from rapidfuzz import fuzz

from apps.api.agents.stage3_summarizer import quote_verifier as qv
from apps.api.services import report_service as rs
from apps.api.services.db_service import supabase

logger = logging.getLogger("apps.api.paper_service")

MAX_REFERENCES = 400
ABSTRACT_PREVIEW_CHARS = 320
FUZZY_THRESHOLD = 92


# ------------------------------------------------------------------------------------------------------------ quote location
def _sub(chars: list[str], idx: list[int], pattern: "re.Pattern[str]", repl: str) -> tuple[list[str], list[int]]:
    """Regex substitution on a character list that keeps, for every remaining character, its index in the original text."""
    s = "".join(chars)
    out_c: list[str] = []
    out_i: list[int] = []
    last = 0
    for m in pattern.finditer(s):
        out_c.extend(chars[last:m.start()])
        out_i.extend(idx[last:m.start()])
        for ch in repl:
            out_c.append(ch)
            out_i.append(idx[m.start()])
        last = m.end()
    out_c.extend(chars[last:])
    out_i.extend(idx[last:])
    return out_c, out_i


def normalize_with_map(text: str) -> tuple[str, list[int]]:
    """quote_verifier._norm(text), plus for each character of the result its index in `text`. (HTML entities are not unescaped here:
    the parser's text does not contain them, and unescaping would break the index map.)"""
    chars, idx = list(text), list(range(len(text)))
    chars, idx = _sub(chars, idx, re.compile(r"-\n"), "")
    chars, idx = _sub(chars, idx, re.compile("­"), "")
    chars = ["-" if c in "‐‑‒–" else c for c in chars]
    chars, idx = _sub(chars, idx, qv._CITATION, " ")
    chars, idx = _sub(chars, idx, re.compile(r"\(\s+"), "(")
    chars, idx = _sub(chars, idx, re.compile(r"\s+\)"), ")")
    chars, idx = _sub(chars, idx, re.compile(r"\s+"), " ")
    chars = [c.lower() if len(c.lower()) == 1 else c for c in chars]
    return "".join(chars), idx


class QuoteLocator:
    """Normalizes one paper's text once, then places any number of quotes in it."""

    def __init__(self, text: str):
        self.text = text
        self.norm, self.idx = normalize_with_map(text) if text else ("", [])

    def _u16(self, i: int) -> int:
        return len(self.text[:i].encode("utf-16-le", "surrogatepass")) // 2

    def locate(self, quote: str) -> list[dict]:
        """[{start, end}] in the text for each piece of the quote (a quote with an elision has several), or [] if any piece cannot be placed."""
        pieces = [qv._norm(p) for p in qv._ELLIPSIS.split(quote or "")]
        pieces = [p for p in pieces if len(p) >= qv.MIN_PIECE_CHARS]
        if not pieces or not self.norm:
            return []
        spans: list[tuple[int, int]] = []
        for piece in pieces:
            pos = self.norm.find(piece)
            if pos >= 0:
                s, e = pos, pos + len(piece)
            else:
                al = fuzz.partial_ratio_alignment(piece, self.norm)
                if al is None or al.score < FUZZY_THRESHOLD or al.dest_end <= al.dest_start:
                    return []
                s, e = al.dest_start, al.dest_end
            spans.append((self.idx[s], self.idx[e - 1] + 1))
        spans.sort()
        return [{"start": self._u16(a), "end": self._u16(b)} for a, b in spans]


# ------------------------------------------------------------------------------------------------------------ small helpers
def _paper_url(p: dict) -> Optional[str]:
    if p.get("doi"):
        return f"https://doi.org/{p['doi']}"
    if p.get("arxiv_id"):
        return f"https://arxiv.org/abs/{p['arxiv_id']}"
    return p.get("pdf_url")


def _select_light(table: str, columns: str, column: str, values: list[str]) -> list[dict]:
    rows: list[dict] = []
    for i in range(0, len(values), 40):
        rows += supabase.table(table).select(columns).in_(column, values[i:i + 40]).execute().data
    return rows


def _evidence(d: Optional[dict]) -> Optional[dict]:
    if not d:
        return None
    return {"level": d.get("evidence_level"), "findings": d.get("total_count"), "quotesFound": d.get("verified_count"), "weight": d.get("weight")}


def _paper_summary(p: dict, topics: dict, parsed: Optional[dict], digest: Optional[dict]) -> dict:
    return {
        "id": str(p["id"]), "title": p.get("title"), "authors": p.get("authors") or [], "year": p.get("year"), "venue": p.get("venue"),
        "source": p.get("source"), "doi": p.get("doi"), "arxivId": p.get("arxiv_id"), "url": _paper_url(p), "pdfUrl": p.get("pdf_url"),
        "citations": p.get("citation_count"), "isPreprint": p.get("is_preprint"), "publishedDate": p.get("published_date"),
        "fieldsOfStudy": p.get("fields_of_study") or [],
        "scores": {"relevance": p.get("relevance_score"), "reliability": p.get("reliability_score"), "combined": p.get("combined_score")},
        "judge": {"relevant": p.get("judge_relevant"), "confidence": p.get("judge_confidence"), "reason": p.get("judge_reason")},
        "tldr": p.get("tldr"), "abstractPreview": (p.get("abstract") or "")[:ABSTRACT_PREVIEW_CHARS],
        "subQuestionId": p.get("sub_question_id"), "subQuestion": topics.get(p.get("sub_question_id")),
        "parse": {"status": "parsed" if parsed else "not_parsed", "parserVersion": (parsed or {}).get("parser_version")},
        "evidence": _evidence(digest),
    }


def _topics_and_digests(query_id: str) -> tuple[dict, list[dict], list[str]]:
    sqs = supabase.table("sub_questions").select("id,main_topic,created_at").eq("query_id", query_id).execute().data
    topics = {s["id"]: s["main_topic"] for s in sqs}
    sq_ids = list(topics)
    digests = rs._latest_generation(rs._select("digests", "sub_question_id", sq_ids)) if sq_ids else []
    return topics, digests, sq_ids


# ------------------------------------------------------------------------------------------------------------ overview
def build_papers_overview(query_id: str) -> Optional[dict]:
    """The retrieval funnel of a run and every paper / web source it kept. Works while the run is going (what has been written so far)."""
    if not supabase.table("research_queries").select("id").eq("id", query_id).execute().data:
        return None
    topics, digests, sq_ids = _topics_and_digests(query_id)
    papers = supabase.table("retrieved_papers").select("*").eq("query_id", query_id).execute().data
    parsed = {str(r["retrieved_paper_id"]): r for r in _select_light("parsed_papers", "id,retrieved_paper_id,parser_version", "retrieved_paper_id",
                                                                      [str(p["id"]) for p in papers])}
    webs = _select_light("web_sources", "id,sub_question_id,url,title,snippet,provider,published_date,reliability_score", "sub_question_id", sq_ids) if sq_ids else []

    by_source: dict[str, dict] = {}
    for d in digests:                       # newest digest per source wins
        by_source.setdefault(str(d["source_id"]), d)
    paper_rows = sorted((_paper_summary(p, topics, parsed.get(str(p["id"])), by_source.get(str(p["id"]))) for p in papers),
                        key=lambda r: -(r["scores"]["combined"] or 0))
    web_rows = sorted(({"id": str(w["id"]), "title": w.get("title"), "url": w.get("url"), "provider": w.get("provider"), "publishedDate": w.get("published_date"),
                        "reliability": w.get("reliability_score"), "snippet": w.get("snippet"), "subQuestionId": w.get("sub_question_id"),
                        "subQuestion": topics.get(w.get("sub_question_id")), "evidence": _evidence(by_source.get(str(w["id"])))} for w in webs),
                      key=lambda r: -(r["reliability"] or 0))
    used_papers = [r for r in paper_rows if r["evidence"]]
    counts = {
        "papersKept": len(paper_rows),
        "papersParsed": sum(1 for r in paper_rows if r["parse"]["status"] == "parsed"),
        "papersUsedAsEvidence": len(used_papers),
        "papersUsedFullText": sum(1 for r in used_papers if r["evidence"]["level"] == "full_text"),
        "papersUsedAbstractOnly": sum(1 for r in used_papers if r["evidence"]["level"] != "full_text"),
        "papersWithPdfLink": sum(1 for r in paper_rows if r["pdfUrl"]),
        "webFound": len(web_rows),
        "webUsedAsEvidence": sum(1 for r in web_rows if r["evidence"]),
        "subQuestions": len(topics),
    }
    return {"id": query_id, "counts": counts, "subQuestions": [{"id": k, "topic": v} for k, v in topics.items()], "papers": paper_rows, "web": web_rows}


# ------------------------------------------------------------------------------------------------------------ one paper
def _valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def build_paper_detail(query_id: str, paper_id: str) -> Optional[dict]:
    """One paper of a run, with its parsed content and the findings taken from it. None if the run has no such paper."""
    if not _valid_uuid(paper_id):
        return None
    rows = supabase.table("retrieved_papers").select("*").eq("id", paper_id).eq("query_id", query_id).execute().data
    if not rows:                                  # also: a paper of another run is not readable through this run's id
        return None
    p = rows[0]
    topics, digests, _ = _topics_and_digests(query_id)
    mine = [d for d in digests if str(d["source_id"]) == str(paper_id)]
    digest = mine[0] if mine else None
    parsed_rows = supabase.table("parsed_papers").select("*").eq("retrieved_paper_id", paper_id).execute().data
    parsed = parsed_rows[0] if parsed_rows else None

    text = (parsed or {}).get("full_text") or ""
    locator = QuoteLocator(text)
    findings = []
    for d in mine:
        for f in rs._as_list(d.get("findings")):
            judge = rs._as_dict(f.get("judge"))
            findings.append({
                "claim": f.get("claim"), "quote": f.get("quote"), "stance": f.get("stance"), "quoteFound": bool(f.get("verified")),
                "subQuestion": topics.get(d.get("sub_question_id")),
                "judgements": [{"aspect": j.get("aspect"), "verdict": j.get("final"), "quoteSupportsClaim": j.get("quote_supports_claim"),
                                "answersAspect": j.get("answers_aspect"), "reason": j.get("reason")} for j in judge.values() if isinstance(j, dict)],
                "spans": locator.locate(f.get("quote") or "") if text else [],
            })

    parsed_view: Optional[dict[str, Any]] = None
    if parsed:
        refs = rs._as_list(parsed.get("cited_references"))
        parsed_view = {
            "parserVersion": parsed.get("parser_version"), "chars": len(text), "text": text,
            "outline": [{"heading": s.get("heading"), "level": s.get("level")} for s in rs._as_list(parsed.get("sections")) if isinstance(s, dict) and s.get("heading")],
            "figures": [{"page": f.get("page"), "label": f.get("label"), "caption": f.get("caption")} for f in rs._as_list(parsed.get("figures")) if isinstance(f, dict)],
            "references": [str(r) for r in refs[:MAX_REFERENCES]], "referenceCount": len(refs),
        }
    return {"paper": _paper_summary(p, topics, parsed, digest), "abstract": p.get("abstract") or (parsed or {}).get("abstract") or "",
            "parsed": parsed_view, "findings": findings}
