"""What the web app needs on top of the stored written report: the evidence behind every sentence, a link from every citation to the parsed paper, and
a richer "Answer". Computed when the report is read (GET /api/research/{id}/written-report); nothing is written to the database and no model is called,
so it works for every stored report, old runs included.

Added to the report (all optional for a client; every field of the stored report stays as it was):

  sentence.citations   [{ref, paperId, parsed, quotes: [{text, findingId, paperId, parsed, relation, evidenceLevel}]}]   (overview.summary, sections[].sentences, conclusion)
        the quotes behind the sentence's claims, grouped by the reference they belong to. `paperId` is a retrieved_papers id: the page of the paper is
        /research/{id}/papers/{paperId}; `parsed` says that TRACE has the parsed text of it; `findingId` is the id of the finding in GET .../papers/{paperId}
        (paper_service.finding_id), so the page can scroll to the highlighted quote. A web source has paperId null: only its url can be opened.
        The citation's own paperId is the paper that holds its first quote (the same document can be several rows, one per sub-question), so the
        findingId of that quote is always on that page; each quote also has its own paperId.
  reference.paper      {id, parsed} for a paper reference (the paper to open from the reference list), null for a web page or a paper the database no longer has
  reference.citedIn    how many sentences of the report cite it
  overview.answer      the answer as parts: {headline, parts[{sectionId, title, sentence, supporting[]}], strength, figures, openQuestions, disputes}

The claim ids of a sentence are the hash of the sub-question id and the claim text (stage5_report.schema.make_claim_id), so the claims are found again in the
stored fact_claims rows without any change to Stage 5. Only the light `schema` module of Stage 5 is imported here: this runs in the API process.
"""
import copy
import logging
import re
from collections import Counter
from typing import Optional

from apps.api.agents.stage5_report.schema import make_claim_id
from apps.api.services import report_service as rs
from apps.api.services.db_errors import valid_uuid
from apps.api.services.paper_service import _select_light, finding_id

logger = logging.getLogger("apps.api.written_report_links")

CITED_RELATIONS = ("supports", "near_match")          # the same as stage5_report.references.CITED_RELATIONS: what a sentence cites
MAX_QUOTES_PER_CITATION = 3
SUPPORTING_PER_PART = 2
MAX_FIGURES = 6
MAX_DISPUTES = 3
TIER_ORDER = {"supported": 0, "partly": 1, "single": 2}          # the tiers of a written sentence; "note" (a template line) is none of them
FIGURE_RE = re.compile(r"\d+(?:\.\d+)?\s?%")
SETTLE_RE = re.compile(r"^\s*The evidence collected does not settle:\s*(.+?)\.?\s*$", re.I | re.S)


class Context:
    """What is read from the database to enrich one report: the claims (by claim id) with their quotes, and which source ids are papers / parsed papers."""

    def __init__(self, claims: Optional[dict] = None, papers: Optional[set] = None, parsed: Optional[set] = None):
        self.claims = claims or {}              # claim id -> {"subQuestionId", "evidence": [{"sourceId", "quote", "relation", "level"}]}
        self.papers = papers or set()           # source ids that are retrieved_papers rows
        self.parsed = parsed or set()           # of those, the ones that have a parsed_papers row


def _norm(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


# ------------------------------------------------------------------------------------------------------------------------------ database
def load_context(report: dict) -> Context:
    """The claims behind the report's sentences and the paper / parsed state of their sources. Reads fact_claims, retrieved_papers and parsed_papers."""
    sq_ids = [str(s["subQuestionId"]) for s in report.get("sections") or [] if s.get("subQuestionId")]
    claims: dict = {}
    for row in rs._select("fact_claims", "sub_question_id", sq_ids) if sq_ids else []:
        text = _norm(row.get("claim"))
        if not text:
            continue
        sq = str(row.get("sub_question_id"))
        evidence = []
        for e in rs._as_list(row.get("evidence")):
            if not isinstance(e, dict):
                continue
            quote, sid = _norm(e.get("quote")), str(e.get("source_id") or "")
            if quote and sid:
                evidence.append({"sourceId": sid, "quote": quote, "relation": str(e.get("relation") or "supports"), "level": e.get("evidence_level")})
        claims[make_claim_id(sq, text)] = {"subQuestionId": sq, "evidence": evidence}
    ids = {ev["sourceId"] for c in claims.values() for ev in c["evidence"]} | {str(i) for r in report.get("references") or [] for i in r.get("sourceIds") or []}
    ids = [i for i in ids if valid_uuid(i)]
    papers = {str(r["id"]) for r in _select_light("retrieved_papers", "id", "id", ids)} if ids else set()
    parsed = {str(r["retrieved_paper_id"]) for r in _select_light("parsed_papers", "retrieved_paper_id", "retrieved_paper_id", sorted(papers))} if papers else set()
    return Context(claims, papers, parsed)


# ------------------------------------------------------------------------------------------------------------------------------ the pure part
def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _sentences(report: dict) -> list:
    """Every sentence dict of the report (answer, sections, conclusion), as the same objects the report holds."""
    out = list((report.get("overview") or {}).get("summary") or [])
    for sec in report.get("sections") or []:
        out += sec.get("sentences") or []
    return out + list(report.get("conclusion") or [])


def enrich_report(report: dict, ctx: Context) -> dict:
    """A copy of the written report with citations, reference.paper / citedIn and overview.answer added. Never raises on a surprising shape of the
    report (a sentence without claimIds simply gets no citations)."""
    out = copy.deepcopy(report)
    refs = [r for r in out.get("references") or [] if isinstance(r, dict) and isinstance(r.get("number"), int)]
    source_to_ref = {str(sid): r["number"] for r in refs for sid in r.get("sourceIds") or []}
    sentences = [s for s in _sentences(out) if isinstance(s, dict)]

    # --- the quotes behind every sentence, grouped by reference
    seen_by_paper: Counter = Counter()
    for s in sentences:
        by_ref: dict = {}
        for cid in s.get("claimIds") or []:
            for ev in (ctx.claims.get(cid) or {}).get("evidence", []):
                n = source_to_ref.get(ev["sourceId"])
                if ev["relation"] not in CITED_RELATIONS or n is None:
                    continue
                entry = by_ref.setdefault(n, {"ref": n, "paperId": None, "parsed": False, "quotes": []})
                fid = finding_id(ev["quote"])
                if len(entry["quotes"]) < MAX_QUOTES_PER_CITATION and all(q["findingId"] != fid for q in entry["quotes"]):
                    is_paper = ev["sourceId"] in ctx.papers
                    entry["quotes"].append({"text": ev["quote"], "findingId": fid, "paperId": ev["sourceId"] if is_paper else None,
                                            "parsed": ev["sourceId"] in ctx.parsed, "relation": ev["relation"], "evidenceLevel": ev.get("level")})
                    if is_paper:
                        seen_by_paper[(n, ev["sourceId"])] += 1
        s["citations"] = [by_ref[n] for n in sorted(by_ref)]

    # --- the paper to open for each reference (the parsed copy first, then the one cited most)
    for r in refs:
        candidates = {sid for sid in map(str, r.get("sourceIds") or []) if sid in ctx.papers} | {pid for (n, pid) in seen_by_paper if n == r["number"]}
        best = min(candidates, key=lambda sid: (sid not in ctx.parsed, -seen_by_paper[(r["number"], sid)], sid), default=None) if r.get("kind") != "web" else None
        r["paper"] = {"id": best, "parsed": best in ctx.parsed} if best else None
        r["citedIn"] = sum(1 for s in sentences if r["number"] in (s.get("refs") or []))
    paper_of = {r["number"]: r["paper"] for r in refs}
    for s in sentences:
        for c in s["citations"]:
            first = next((q for q in c["quotes"] if q["paperId"]), None)            # the same document can be several rows (one per sub-question): link to the one that holds the quote
            p = {"id": first["paperId"], "parsed": first["parsed"]} if first else paper_of.get(c["ref"])
            c["paperId"], c["parsed"] = (p["id"], p["parsed"]) if p else (None, False)

    answer = build_answer(out, ctx, refs)
    if answer is not None:
        out.setdefault("overview", {})["answer"] = answer
    return out


def build_answer(report: dict, ctx: Context, refs: list) -> Optional[dict]:
    """The answer as parts. None when the report has no answer sentence. See the module docstring for the fields."""
    overview = report.get("overview") or {}
    summary = [s for s in overview.get("summary") or [] if isinstance(s, dict)]
    sections = [s for s in report.get("sections") or [] if isinstance(s, dict)]
    if not summary:
        return None
    by_sq = {str(s.get("subQuestionId")): s for s in sections}
    claim_section: dict = {}
    for sec in sections:
        for sen in sec.get("sentences") or []:
            for cid in sen.get("claimIds") or []:
                claim_section.setdefault(cid, sec)

    def section_of(sen: dict) -> Optional[dict]:
        votes: Counter = Counter()
        for cid in sen.get("claimIds") or []:
            sec = claim_section.get(cid)
            if sec is None and cid in ctx.claims:
                sec = by_sq.get(ctx.claims[cid]["subQuestionId"])
            if sec is not None:
                votes[sections.index(sec)] += 1
        return sections[min(votes, key=lambda i: (-votes[i], i))] if votes else None

    statements = [(i, s) for i, s in enumerate(summary) if s.get("tier") in TIER_ORDER]
    used = {cid for _, s in statements for cid in s.get("claimIds") or []}
    parts = []
    for i, sen in statements:
        sec = section_of(sen)
        supporting = []
        if sec is not None:
            pool = [x for x in sec.get("sentences") or [] if x.get("tier") in TIER_ORDER and not (set(x.get("claimIds") or []) & used)]
            pool.sort(key=lambda x: (TIER_ORDER[x["tier"]], -len(x.get("refs") or [])))          # stable: the report's own order breaks ties
            for x in pool[:SUPPORTING_PER_PART]:
                supporting.append(copy.deepcopy(x))
                used |= set(x.get("claimIds") or [])
        parts.append({"sentenceIndex": i, "sectionId": sec.get("id") if sec else None, "title": sec.get("title") if sec else None,
                      "sentence": copy.deepcopy(sen), "supporting": supporting})

    open_questions: list = []
    for s in summary:
        m = SETTLE_RE.match(s.get("text") or "") if s.get("tier") == "note" else None
        if m:
            open_questions += [q.strip() for q in m.group(1).split(";") if q.strip()]

    disputes = [{"sectionId": sec.get("id"), "title": sec.get("title"), "claimA": d.get("claimA"), "claimB": d.get("claimB"),
                 "refs": [n for n in ((d.get("sideA") or {}).get("ref"), (d.get("sideB") or {}).get("ref")) if isinstance(n, int)]}
                for sec in sections for d in sec.get("disagreements") or [] if isinstance(d, dict)]

    figures, seen = [], set()
    for i, sen in statements:
        for m in FIGURE_RE.finditer(sen.get("text") or ""):
            value = re.sub(r"\s", "", m.group())
            if (value, i) not in seen and len(figures) < MAX_FIGURES:
                seen.add((value, i))
                figures.append({"value": value, "sentenceIndex": i, "refs": list(sen.get("refs") or [])})

    by_number = {r["number"]: r for r in refs}
    cited = sorted({n for _, s in statements for n in s.get("refs") or []})
    tiers = Counter(s["tier"] for _, s in statements)
    counts = overview.get("counts") or {}
    strength = {"statements": len(statements), "byTier": {t: tiers.get(t, 0) for t in TIER_ORDER}, "documents": len(cited),
                "fullTextDocuments": sum(1 for n in cited if (by_number.get(n) or {}).get("evidenceLevel") == "full_text"),
                "documentsInReport": counts.get("documents"), "partsCovered": len({p["sectionId"] for p in parts if p["sectionId"]}), "sections": len(sections),
                "disagreements": len(disputes), "openQuestions": len(open_questions)}
    bits = [f"{_plural(len(statements), 'statement', 'statements')} from {_plural(len(cited), 'document', 'documents')}"]
    if tiers.get("supported"):
        bits.append(f"{tiers['supported']} stated by two or more documents")
    if tiers.get("partly"):
        bits.append(f"{tiers['partly']} partly supported")
    if tiers.get("single"):
        bits.append(f"{tiers['single']} from a single source, not confirmed")
    if disputes:
        bits.append(f"{_plural(len(disputes), 'disagreement', 'disagreements')} between sources in the report")
    if open_questions:
        bits.append(f"{_plural(len(open_questions), 'open question', 'open questions')}")
    strength["line"] = "; ".join(bits) + "."
    return {"headline": {"sentenceIndex": statements[0][0]} if statements else None, "parts": parts, "strength": strength, "figures": figures,
            "openQuestions": open_questions, "disputes": {"count": len(disputes), "items": disputes[:MAX_DISPUTES]}}


# ------------------------------------------------------------------------------------------------------------------------------ the entry point
def enrich_view(view: dict, query_id: str) -> dict:
    """`view` is report_service.written_report_view(row). Returns it with the enriched report. The report must never be lost because of this: any failure
    (a database hiccup, a surprising shape) is logged and the view is returned as it was stored."""
    from apps.api.services.db_errors import read_with_retry
    try:
        report = view.get("report") or {}
        if not report:
            return view
        ctx = read_with_retry(load_context, report)
        return {**view, "report": enrich_report(report, ctx)}
    except Exception as e:                                  # noqa: BLE001
        logger.warning("written report of %s returned without citations and answer parts: %s: %s", query_id, type(e).__name__, str(e)[:200])
        return view
