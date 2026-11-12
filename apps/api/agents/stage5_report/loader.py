"""Reads what Stage 5 needs about a run and returns it as ONE plain dict (no pydantic, no Claim objects: tiers.build_claims makes those).

Two ways in, same dict:
  load_inputs(query_id, db=None)   from the database (a finished run, an old run, the API). Reuses report_service's helpers (`_select`,
                                   `_latest_generation`, `_loop2_view`, `_as_list`) and the read pattern `read_with_retry` (one retry on a dropped
                                   connection, then DatabaseUnavailable); the url of a paper is paper_service's rule, not a new copy.
  from_state(state, db=None)       inside a live run: fact_claims, contradictions (when the state has them), coverage and the plan come from the
                                   state; the database is read only for the source metadata (state sources have no ids) and the run's created_at.

Shape:
  {"query_id", "question", "created_at", "domain_context", "domain_anchor",
   "fact_ran": bool            any fact_claims row exists (Stage 4 ran and produced claims),
   "fact_error": str | None    Stage 4 failed as a whole (state only: fact_summary == {"error": ...}),
   "status_hints": {...}       origin, found, fact_failed_sub_questions, coverage_missing, no_claims_sub_questions, judge_failures, sources_without_metadata,
   "sub_questions": [{"id", "title", "detail_questions", "coverage": {...gaps...}, "claims": [Stage 4 rows], "contradictions": [rows],
                      "fact_summary": dict | None (state only), "fact_error": str | None}],      # in created_at / planner order
   "sources": {source_id: {kind, title, authors, year, venue, doi, arxiv_id, pdf_url, url, provider, published, evidence_level}}}

The database has no fact_summary, so a run read from it cannot tell "Stage 4 found nothing" from "Stage 4 failed" for a sub-question: the hints say
which sub-questions have no claims and Stage 5 words that as "no claims were checked", never as a verdict.
"""
import json
import logging
from typing import Any, Optional

from apps.api.services.db_errors import read_with_retry, valid_uuid

logger = logging.getLogger("apps.api.stage5_report")

CLAIM_KEYS = ("claim", "label", "confidence", "support_doc_count", "contra_doc_count", "contested", "evidence", "sub_question_id")
LEVEL_RANK = {"full_text": 3, "abstract": 2, "web_snippet": 1}


def _rs():
    from apps.api.services import report_service        # imported late: it creates the database client
    return report_service


def _as_list(value: Any) -> list:
    return _rs()._as_list(value)


def _as_dict(value: Any) -> dict:
    return _rs()._as_dict(value)


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """obj[key] for a dict, obj.key for an object (the graph state and the task plan are pydantic models; tests pass dicts)."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _select(db, table: str, column: str, values) -> list:
    """All rows of `table` whose `column` is in `values`. With no `db` this IS report_service._select (the real client); with a `db` (a
    supabase-like object, used by tests) the same chunked query is made on it."""
    if db is None:
        return _rs()._select(table, column, values)
    values = [v for v in dict.fromkeys(values) if v]
    rows: list = []
    for i in range(0, len(values), 40):
        rows += db.table(table).select("*").in_(column, values[i:i + 40]).execute().data
    return rows


def _client(db):
    return db if db is not None else _rs().supabase


# --------------------------------------------------------------------------------------------------------------------------- coverage
def coverage_view(cov: Optional[dict]) -> dict:
    """The Stage 3 gaps of one sub-question as plain lists of text. `present` is False when Stage 3 left no coverage row/entry for it."""
    if not isinstance(cov, dict) or not cov:
        return {"present": False, "sufficient": None, "source_count": None, "full_text_source_count": None, "uncovered_details": [],
                "uncovered_aspects": [], "unjudged_aspects": [], "known_gaps": [], "covered_by_synthesis": [], "digest_failures": 0, "fallback_reason": None}
    loop2 = _rs()._loop2_view(cov) or {}
    texts = lambda v: [t for t in _as_list(v) if isinstance(t, str) and t.strip()]      # noqa: E731
    failures = cov.get("digest_failures")
    return {"present": True, "sufficient": bool(cov.get("sufficient")), "source_count": cov.get("source_count"),
            "full_text_source_count": cov.get("full_text_source_count"),
            "uncovered_details": texts(cov.get("uncovered_details")), "uncovered_aspects": texts(cov.get("uncovered_aspects")),
            "unjudged_aspects": texts(cov.get("unjudged_aspects")), "known_gaps": texts(loop2.get("knownGapsNoEvidence")),
            "covered_by_synthesis": [a["text"] for a in loop2.get("aspects") or [] if a.get("how") == "synthesis" and isinstance(a.get("text"), str)],
            "digest_failures": len(failures) if isinstance(failures, (list, dict)) else (failures if isinstance(failures, int) else 0),
            "fallback_reason": cov.get("fallback_reason") or None}


# ---------------------------------------------------------------------------------------------------------------------------- sources
def _best_level(levels: list) -> Optional[str]:
    levels = [l for l in levels if l in LEVEL_RANK]
    return max(levels, key=lambda l: LEVEL_RANK[l]) if levels else None


def source_metadata(db, source_ids, levels: Optional[dict] = None) -> dict:
    """{source_id: metadata} for the ids that Stage 4 evidence points at (a paper row or a web row). `levels` = {source_id: evidence level} from the digests."""
    from apps.api.services.paper_service import _paper_url
    ids = [i for i in dict.fromkeys(str(s) for s in source_ids if s) if valid_uuid(i)]
    levels = levels or {}
    out: dict = {}
    for p in _select(db, "retrieved_papers", "id", ids):
        sid = str(p["id"])
        out[sid] = {"kind": "paper", "title": p.get("title") or "", "authors": _as_list(p.get("authors")), "year": p.get("year"), "venue": p.get("venue"),
                    "doi": p.get("doi"), "arxiv_id": p.get("arxiv_id"), "pdf_url": p.get("pdf_url"), "url": _paper_url(p), "provider": p.get("source"),
                    "published": p.get("published_date"), "evidence_level": levels.get(sid)}
    for w in _select(db, "web_sources", "id", [i for i in ids if i not in out]):
        sid = str(w["id"])
        out[sid] = {"kind": "web", "title": w.get("title") or "", "authors": [], "year": None, "venue": None, "doi": None, "arxiv_id": None, "pdf_url": None,
                    "url": w.get("url"), "provider": w.get("provider"), "published": w.get("published_date"),
                    "evidence_level": levels.get(sid) or "web_snippet"}
    return out


def _digest_levels(digest_rows: list) -> dict:
    by_id: dict = {}
    for d in digest_rows:
        by_id.setdefault(str(d.get("source_id")), []).append(d.get("evidence_level"))
    return {sid: _best_level(lv) for sid, lv in by_id.items()}


def _evidence_source_ids(fact_rows: list) -> list:
    return [str(e.get("source_id")) for r in fact_rows for e in _as_list(r.get("evidence")) if isinstance(e, dict) and e.get("source_id")]


# ---------------------------------------------------------------------------------------------------------------------------- assemble
def _claim_row(row: dict) -> dict:
    out = {k: row.get(k) for k in CLAIM_KEYS}
    out["evidence"] = [e for e in _as_list(row.get("evidence")) if isinstance(e, dict)]
    out["contested"] = bool(row.get("contested"))
    return out


def _assemble(*, origin: str, query_id: str, question: str, created_at: Optional[str], sqs: list, covs: dict, fact_rows: list, contra_rows: list,
              sources: dict, fact_error: Optional[str] = None, fact_summary: Optional[dict] = None, domain_context: str = "", domain_anchor: str = "") -> dict:
    """The output dict from rows. `sqs` = [{"id", "main_topic", "detail_questions"}] already in section order."""
    sub_questions, no_claims, failed, coverage_missing, judge_failures = [], [], [], [], 0
    for sq in sqs:
        sid = str(sq["id"])
        mine = [_claim_row(r) for r in fact_rows if str(r.get("sub_question_id")) == sid]
        for r in mine:
            r["sub_question_id"] = sid
        summary = fact_summary.get(sid) if isinstance(fact_summary, dict) and isinstance(fact_summary.get(sid), dict) else None
        err = str(summary["error"]) if summary and summary.get("error") else None
        if err:
            failed.append(sid)
        judge_failures += int(summary.get("judge_failures") or 0) if summary and not err else 0
        cov = coverage_view(covs.get(sid))
        if not cov["present"]:
            coverage_missing.append(sid)
        if not mine:
            no_claims.append(sid)
        sub_questions.append({"id": sid, "title": sq.get("main_topic") or "", "detail_questions": [d for d in _as_list(sq.get("detail_questions")) if isinstance(d, str)],
                              "coverage": cov, "claims": mine, "contradictions": [dict(r) for r in contra_rows if str(r.get("sub_question_id")) == sid],
                              "fact_summary": summary, "fact_error": err})
    cited = set(_evidence_source_ids(fact_rows))
    return {"query_id": query_id, "question": question, "created_at": created_at, "domain_context": domain_context, "domain_anchor": domain_anchor,
            "fact_ran": bool(fact_rows), "fact_error": fact_error,
            "status_hints": {"origin": origin, "found": True, "fact_failed_sub_questions": failed, "coverage_missing": coverage_missing,
                             "no_claims_sub_questions": no_claims, "judge_failures": judge_failures if fact_summary else None,
                             "sources_without_metadata": len(cited - set(sources))},
            "sub_questions": sub_questions, "sources": sources}


def _empty(query_id: str, origin: str) -> dict:
    return {"query_id": query_id, "question": "", "created_at": None, "domain_context": "", "domain_anchor": "", "fact_ran": False, "fact_error": None,
            "status_hints": {"origin": origin, "found": False, "fact_failed_sub_questions": [], "coverage_missing": [], "no_claims_sub_questions": [],
                             "judge_failures": None, "sources_without_metadata": 0}, "sub_questions": [], "sources": {}}


# ------------------------------------------------------------------------------------------------------------------------------ database
def _load(query_id: str, db) -> dict:
    rs = _rs()
    rq = _client(db).table("research_queries").select("*").eq("id", query_id).execute().data
    if not rq:
        return _empty(query_id, "db")
    sqs = sorted(_client(db).table("sub_questions").select("*").eq("query_id", query_id).execute().data, key=lambda s: str(s.get("created_at") or ""))
    ids = [s["id"] for s in sqs]
    covs = {c["sub_question_id"]: c for c in sorted(rs._latest_generation(_select(db, "coverage_results", "sub_question_id", ids)),
                                                    key=lambda c: str(c.get("created_at") or ""))}
    fact_rows = _select(db, "fact_claims", "sub_question_id", ids)
    contra_rows = _select(db, "contradictions", "sub_question_id", ids)
    try:                                                    # the digests only tell the evidence level of a source; a failure here is not worth the report
        digests = rs._latest_generation(_select(db, "digests", "sub_question_id", ids))
    except Exception as e:                                  # noqa: BLE001
        logger.warning("digests could not be read for evidence levels: %s", e)
        digests = []
    sources = source_metadata(db, _evidence_source_ids(fact_rows), _digest_levels(digests))
    return _assemble(origin="db", query_id=query_id, question=rq[0].get("raw_query") or "", created_at=rq[0].get("created_at"), sqs=sqs, covs=covs,
                     fact_rows=fact_rows, contra_rows=contra_rows, sources=sources)


def load_inputs(query_id: str, *, db=None) -> dict:
    """The Stage 5 input of a stored run (see the module docstring for the shape). An unknown id gives an empty dict shape with
    status_hints["found"] False. Raises DatabaseUnavailable when the database stays unreachable after one retry (the caller turns that into a failure)."""
    return read_with_retry(_load, str(query_id), db)


# --------------------------------------------------------------------------------------------------------------------------------- state
def from_state(state: Any, *, db=None, created_at: Optional[str] = None) -> dict:
    """The same dict from the graph state of a live run. `state` may be the SharedResearchState or a dict with raw_query, query_id, task_plan,
    fact_claims, fact_summary, coverage and (when the node has them) contradictions. Missing contradictions are read from the database; if the
    database cannot be read the source metadata is left empty (the reference list then uses the titles in the evidence) and the hints say so."""
    plan = _get(state, "task_plan")
    qid = str(_get(state, "query_id") or _get(plan, "query_id") or "")
    sqs = [{"id": str(_get(s, "id")), "main_topic": _get(s, "main_topic") or "", "detail_questions": list(_get(s, "detail_questions") or [])}
           for s in (_get(plan, "sub_questions") or [])]
    fact_rows = [r for r in (_get(state, "fact_claims") or []) if isinstance(r, dict)]
    summary = _get(state, "fact_summary") or {}
    fact_error = str(summary["error"]) if isinstance(summary, dict) and summary.get("error") else None
    covs = {str(k): v for k, v in (_get(state, "coverage") or {}).items()} if isinstance(_get(state, "coverage"), dict) else {}
    contra = _get(state, "contradictions")
    ids = [s["id"] for s in sqs]
    try:
        if contra is None:
            contra = _select(db, "contradictions", "sub_question_id", ids) if ids else []
        sources = source_metadata(db, _evidence_source_ids(fact_rows), _digest_levels([d for d in (_get(state, "digests") or []) if isinstance(d, dict)]))
        if created_at is None and qid:
            rq = _client(db).table("research_queries").select("*").eq("id", qid).execute().data
            created_at = rq[0].get("created_at") if rq else None
    except Exception as e:                                  # noqa: BLE001  (the database is only for metadata here: never fail the report for it)
        logger.warning("Stage 5 could not read source metadata from the database: %s", e)
        contra, sources = contra or [], {}
    out = _assemble(origin="state", query_id=qid, question=str(_get(state, "raw_query") or _get(plan, "raw_query") or ""), created_at=created_at, sqs=sqs,
                    covs=covs, fact_rows=fact_rows, contra_rows=[r for r in contra if isinstance(r, dict)], sources=sources,
                    fact_error=fact_error, fact_summary={k: v for k, v in summary.items() if k != "error"} if isinstance(summary, dict) else None,
                    domain_context=str(_get(plan, "domain_context") or ""), domain_anchor=str(_get(plan, "domain_anchor") or ""))
    return out
