"""Read a finished (or half-finished) run from the database and shape it for the frontend. No LLM call, no writes.

Stage 4 (fact check) is not wired into the graph and Stage 5 (the written report) is not built, so the "report" is an EVIDENCE report:
per sub-question the sources that were read, the findings taken from them (claim, verbatim quote, whether the quote was found in the source,
the independent judge's verdicts) and whether the evidence is sufficient, with the aspects that stay uncovered named explicitly. The
frontend must show that gap and must not present this as a finished answer.
"""
import json
import logging
from datetime import datetime
from typing import Any, Iterable, Optional

from apps.api.services.db_service import supabase

logger = logging.getLogger("apps.api.report_service")

GENERATION_WINDOW_S = 180          # rows written by one Stage 3 run share (almost) the same created_at; a rerun of Stage 3 writes new rows
NOT_RUN = ("factcheck", "report")
LIMITATIONS = [
    "Stage 4 (fact checking) is not part of the pipeline yet: findings are verified only in the sense that their quote was found in the source, "
    "and judged by an independent model against the aspect they should answer. Nothing checks that a claim is true.",
    "Stage 5 (the written report) is not built: this is the collected evidence, not an answer.",
    "Retrieval can only reach what the sources expose: papers behind publisher bot protection or without an open copy are read as abstracts or not at all.",
]


# ------------------------------------------------------------------------------------------------------------ database reads
def _select(table: str, column: str, values: Iterable[str]) -> list[dict]:
    """All rows of `table` whose `column` is in `values` (in chunks, because the URL of one request is limited)."""
    values = [v for v in dict.fromkeys(values) if v]
    rows: list[dict] = []
    for i in range(0, len(values), 40):
        rows += supabase.table(table).select("*").in_(column, values[i:i + 40]).execute().data
    return rows


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _latest_generation(rows: list[dict]) -> list[dict]:
    """Per sub-question keep only the rows of its newest Stage 3 run."""
    newest: dict[str, datetime] = {}
    for r in rows:
        t = _ts(r["created_at"])
        if r["sub_question_id"] not in newest or t > newest[r["sub_question_id"]]:
            newest[r["sub_question_id"]] = t
    return [r for r in rows if (newest[r["sub_question_id"]] - _ts(r["created_at"])).total_seconds() <= GENERATION_WINDOW_S]


def _as_list(value: Any) -> list:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return []
    return value if isinstance(value, list) else []


def _as_dict(value: Any) -> dict:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return {}
    return value if isinstance(value, dict) else {}


# ------------------------------------------------------------------------------------------------------------------ sessions
def session_from_db(query_id: str) -> Optional[dict]:
    """The status of a run that is not in memory (finished before a restart, or started elsewhere); None if the id is unknown.
    A run with a plan but no coverage rows for every sub-question is reported as failed ("interrupted"): the process that ran it is gone."""
    try:
        rq = supabase.table("research_queries").select("*").eq("id", query_id).execute().data
    except Exception:
        return None                                     # a malformed id (not a uuid) is simply "not found"
    if not rq:
        return None
    sqs = supabase.table("sub_questions").select("id").eq("query_id", query_id).execute().data
    covs = supabase.table("coverage_results").select("sub_question_id").eq("query_id", query_id).execute().data
    done = bool(sqs) and {c["sub_question_id"] for c in covs} >= {s["id"] for s in sqs}
    stages = {"planner": "completed" if sqs else "failed", "retrieval": "completed" if done else "unknown",
              "summarizer": "completed" if done else "unknown", "factcheck": "not_built", "report": "not_built"}
    return {"id": query_id, "question": rq[0]["raw_query"], "status": "completed" if done else "failed", "createdAt": rq[0].get("created_at"),
            "startedAt": None, "finishedAt": None, "error": None if done else "The run did not finish (the server restarted or the run was stopped).",
            "stages": stages}


def list_sessions(limit: int = 20) -> list[dict]:
    """The latest runs stored in the database, newest first (status from the coverage rows, like session_from_db)."""
    rqs = supabase.table("research_queries").select("*").order("created_at", desc=True).limit(limit).execute().data
    ids = [r["id"] for r in rqs]
    sqs = _select("sub_questions", "query_id", ids)
    covs = _select("coverage_results", "query_id", ids)
    out = []
    for r in rqs:
        mine = {s["id"] for s in sqs if s["query_id"] == r["id"]}
        done = bool(mine) and {c["sub_question_id"] for c in covs if c["query_id"] == r["id"]} >= mine
        out.append({"id": r["id"], "question": r["raw_query"], "status": "completed" if done else "failed", "createdAt": r.get("created_at")})
    return out


# --------------------------------------------------------------------------------------------------------------- aspect texts
def _cached_aspects(detail_questions: list[str], sub_question_id: str, main_topic: str, cov: dict) -> Optional[list[str]]:
    """The aspect texts of a stored run, rebuilt from the aspect cache only (reports/aspect_cache.json); None when a detail is not in the
    cache or the run used the legacy embedding merge. The database stores aspect INDEXES, not texts; a missing cache is not an error."""
    from apps.api.agents.stage3_summarizer import detail_aspects as da
    if da.run_merge_mode(cov) == "embedding":
        return None
    cache = da._load_cache()
    aspects, a2d = [], []
    for i, detail in enumerate(detail_questions):
        got = cache.get(da._cache_key(sub_question_id, detail))
        if got is None:
            return None
        aspects += got
        a2d += [i] * len(got)
    aspects, a2d, _ = da._merge_near_duplicate_aspects(aspects, a2d, mode=da.run_merge_mode(cov))[:3]
    aspects, _, _ = da.with_topic_aspect(aspects, a2d, detail_questions, main_topic, enabled=da.run_topic_aspect(cov))
    return aspects


def _loop2_view(cov: dict) -> Optional[dict]:
    """What Loop 2 did for this sub-question (stored in judge_stats['loop2']); None when it did not run. knownGaps are the aspects that stay
    uncovered after the search (or were not searched): the report says "evidence not found" for them instead of hiding them."""
    info = _as_dict(_as_dict(cov.get("judge_stats")).get("loop2"))
    if not info:
        return None
    aspects = _as_dict(info.get("aspects"))
    return {"searched": info.get("searched"), "covered": info.get("covered"), "seconds": info.get("seconds"), "triage": info.get("triage"),
            "coveredBySynthesis": info.get("covered_by_synthesis"), "gapRule": info.get("gap_rule"), "sufficientStrict": info.get("sufficient_strict"),
            "knownGapsNoEvidence": _as_list(info.get("known_gaps_no_evidence")),
            "steps": [{"step": s.get("step"), "aspects": len(_as_list(s.get("aspects"))), "newSources": s.get("new_sources"),
                       "newVerifiedFindings": s.get("new_verified"), "covered": len(_as_list(s.get("covered"))), "seconds": s.get("seconds")}
                      for s in _as_list(info.get("steps")) if isinstance(s, dict)],
            "aspects": [{"text": t, "status": a.get("status"), "coveredBy": a.get("covered_by"), "how": a.get("how"), "nearMiss": a.get("near_miss"),
                         "steps": _as_list(a.get("steps"))}
                        for t, a in aspects.items() if isinstance(a, dict)],
            "knownGaps": [t for t, a in aspects.items() if isinstance(a, dict) and str(a.get("status", "")).startswith("known_gap")]}


def _aspect_rows(aspects: Optional[list[str]], cov: dict) -> list[dict]:
    """One row per aspect: text, state, number of judge 'yes' verdicts and of distinct sources behind them."""
    evidence = _as_dict(cov.get("aspect_evidence"))
    uncovered = set(_as_list(cov.get("uncovered_aspects")))
    unjudged = set(_as_list(cov.get("unjudged_aspects")))
    reasons = _as_dict(cov.get("uncovered_reasons"))
    texts = aspects if aspects is not None else [None] * (max([int(k) for k in evidence if str(k).isdigit()] + [-1]) + 1)
    rows = []
    for i, text in enumerate(texts):
        items = [x for x in _as_list(evidence.get(str(i))) if isinstance(x, dict)]
        yes = [x for x in items if x.get("verdict") == "yes"]
        if text in unjudged:
            state = "unjudged"
        elif text in uncovered:
            state = reasons.get(text, "uncovered")
        else:
            state = "covered" if text is not None else "unknown"
        rows.append({"index": i, "text": text, "state": state, "yesVerdicts": len(yes), "sources": len({x.get("source_id") for x in yes}),
                     "coveredBy": "synthesis" if state == "covered" and any(x.get("synthesis") for x in items) else ("single_claims" if state == "covered" else None)})
    return rows


# ------------------------------------------------------------------------------------------------------------------- the report
def _source_view(digest: dict, papers: dict, webs: dict) -> dict:
    sid = str(digest["source_id"])
    findings = []
    for f in _as_list(digest.get("findings")):
        judge = _as_dict(f.get("judge"))
        findings.append({"claim": f.get("claim"), "quote": f.get("quote"), "stance": f.get("stance"), "quoteFound": bool(f.get("verified")),
                         "judgements": [{"aspect": j.get("aspect"), "verdict": j.get("final"), "quoteSupportsClaim": j.get("quote_supports_claim"),
                                         "answersAspect": j.get("answers_aspect"), "reason": j.get("reason")}
                                        for j in judge.values() if isinstance(j, dict)]})
    loop2_steps = {_as_dict(f.get("loop2")).get("step") for f in _as_list(digest.get("findings")) if f.get("loop2")}
    base = {"foundByLoop2Step": next(iter(loop2_steps)) if loop2_steps else None, "id": sid, "type": digest.get("source_type"), "title": digest.get("source_title"), "evidenceLevel": digest.get("evidence_level"),
            "weight": digest.get("weight"), "findingsTotal": digest.get("total_count"), "findingsQuoteFound": digest.get("verified_count"),
            "findings": findings}
    if digest.get("source_type") == "paper" and sid in papers:
        p = papers[sid]
        base.update({"authors": p.get("authors"), "year": p.get("year"), "venue": p.get("venue"), "doi": p.get("doi"), "arxivId": p.get("arxiv_id"),
                     "url": (f"https://doi.org/{p['doi']}" if p.get("doi") else f"https://arxiv.org/abs/{p['arxiv_id']}" if p.get("arxiv_id") else p.get("pdf_url")),
                     "citations": p.get("citation_count"), "origin": p.get("source")})
    elif sid in webs:
        w = webs[sid]
        base.update({"url": w.get("url"), "provider": w.get("provider"), "publishedDate": w.get("published_date")})
    return base


def build_report(query_id: str) -> Optional[dict]:
    """The evidence report of a run, or None if the id is unknown."""
    rq = supabase.table("research_queries").select("*").eq("id", query_id).execute().data
    if not rq:
        return None
    sqs = sorted(supabase.table("sub_questions").select("*").eq("query_id", query_id).execute().data, key=lambda s: s["created_at"])
    sq_ids = [s["id"] for s in sqs]
    covs = {c["sub_question_id"]: c for c in sorted(_latest_generation(_select("coverage_results", "sub_question_id", sq_ids)),
                                                    key=lambda c: c["created_at"])}
    digests = _latest_generation(_select("digests", "sub_question_id", sq_ids))
    papers = {str(p["id"]): p for p in _select("retrieved_papers", "id", [d["source_id"] for d in digests if d.get("source_type") == "paper"])}
    webs = {str(w["id"]): w for w in _select("web_sources", "id", [d["source_id"] for d in digests if d.get("source_type") != "paper"])}

    sub_questions, limitations = [], list(LIMITATIONS)
    for sq in sqs:
        cov = covs.get(sq["id"])
        mine = [d for d in digests if d["sub_question_id"] == sq["id"]]
        details = _as_list(sq.get("detail_questions"))
        view: dict = {"id": sq["id"], "topic": sq["main_topic"], "detailQuestions": details,
                      "sources": [_source_view(d, papers, webs) for d in sorted(mine, key=lambda d: -(d.get("weight") or 0))],
                      "coverage": None}
        if cov:
            aspects = _cached_aspects(details, sq["id"], sq["main_topic"], cov)
            view["coverage"] = {"sufficient": bool(cov.get("sufficient")), "judgeUsed": cov.get("judge_used"), "sourceCount": cov.get("source_count"),
                                "fullTextSourceCount": cov.get("full_text_source_count"), "digestFailures": cov.get("digest_failures"),
                                "aspects": _aspect_rows(aspects, cov), "uncoveredAspects": _as_list(cov.get("uncovered_aspects")),
                                "unjudgedAspects": _as_list(cov.get("unjudged_aspects")), "fallbackReason": cov.get("fallback_reason"),
                                "loop2": _loop2_view(cov)}
            if not cov.get("sufficient"):
                limitations.append(f"Evidence is not sufficient for: {sq['main_topic']}")
            for gap in (view["coverage"]["loop2"] or {}).get("knownGapsNoEvidence") or []:
                limitations.append(f"Evidence not found for: {gap} (searched again; part of: {sq['main_topic']})")
            for a in (view["coverage"]["loop2"] or {}).get("aspects") or []:
                if a.get("how") == "synthesis":
                    limitations.append(f"Covered by combining findings of several sources, not by one source: {a.get('text')}")
        else:
            limitations.append(f"Stage 3 did not finish for: {sq['main_topic']}")
        sub_questions.append(view)

    done = [s for s in sub_questions if s["coverage"]]
    return {"id": query_id, "question": rq[0]["raw_query"], "createdAt": rq[0].get("created_at"),
            "stages": {"planner": "completed" if sqs else "unknown", "retrieval": "completed" if sqs else "unknown",
                       "summarizer": "completed" if sqs and len(done) == len(sqs) else "incomplete", **{s: "not_built" for s in NOT_RUN}},
            "totals": {"subQuestions": len(sqs), "subQuestionsSufficient": sum(1 for s in done if s["coverage"]["sufficient"]),
                       "sources": sum(len(s["sources"]) for s in sub_questions),
                       "findings": sum(f for s in sub_questions for src in s["sources"] for f in [len(src["findings"])]),
                       "findingsQuoteFound": sum(1 for s in sub_questions for src in s["sources"] for f in src["findings"] if f["quoteFound"])},
            "subQuestions": sub_questions, "limitations": limitations}
