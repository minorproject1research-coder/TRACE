import json
import logging
import os
import re
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

_url = os.environ["SUPABASE_URL"]
_key = os.environ["SUPABASE_SERVICE_KEY"]

supabase: Client = create_client(_url, _key)

logger = logging.getLogger("apps.api.services.db")

IST = timezone(timedelta(hours=5, minutes=30))


def _now_ist() -> str:
    return datetime.now(IST).isoformat()


def write_task_plan(plan) -> None:
    sub_q_rows, query_rows = plan.to_supabase_rows()

    supabase.table("research_queries").upsert({
        "id": plan.query_id,
        "raw_query": plan.raw_query,
        "created_at": _now_ist(),
    }).execute()

    if sub_q_rows:
        for row in sub_q_rows:
            row["created_at"] = _now_ist()
        supabase.table("sub_questions").upsert(sub_q_rows).execute()

    if query_rows:
        for row in query_rows:
            row["created_at"] = _now_ist()
        supabase.table("queries").insert(query_rows).execute()


def write_retrieved_papers(query_id: str, papers: list[dict]) -> None:
    """Store retrieved papers in the database, linked to the research query."""
    if not papers:
        return

    rows = []
    for paper in papers:
        verdict = paper.get("relevance_verdict") or {}
        rows.append({
            "query_id": query_id,
            "sub_question_id": paper.get("sub_question_id"),
            "judge_relevant": verdict.get("relevant"),
            "judge_confidence": verdict.get("confidence"),
            "judge_reason": verdict.get("reason"),
            "reliability_score": paper.get("reliability_score"),
            "relevance_score": paper.get("relevance_score"),
            "combined_score": paper.get("combined_score"),
            "title": paper.get("title", ""),
            "abstract": paper.get("abstract", ""),
            "authors": paper.get("authors", []),
            "year": paper.get("year"),
            "venue": paper.get("venue"),
            "citation_count": paper.get("citation_count"),
            "influential_citation_count": paper.get("influential_citation_count"),
            "is_preprint": paper.get("is_preprint", False),
            "source": paper.get("source", "unknown"),
            "arxiv_id": paper.get("arxiv_id"),
            "doi": paper.get("doi"),
            "pdf_url": paper.get("pdf_url"),
            "published_date": paper.get("published_date"),
            "tldr": paper.get("tldr"),
            "fields_of_study": paper.get("fields_of_study", []),
            "query_variants_matched": paper.get("query_variant_matched", []),
        })

    supabase.table("retrieved_papers").insert(rows).execute()


def write_web_sources(sources: list) -> None:
    """Store retrieved web sources (from Tavily/Exa/Parallel) in the database,
    linked to the sub-question and query that found them."""
    if not sources:
        return

    now = _now_ist()
    rows = [
        {
            "sub_question_id": s.sub_question_id,
            "url": s.url,
            "title": s.title,
            "snippet": s.snippet,
            "published_date": s.published_date,
            "provider": s.provider,
            "reliability_score": s.reliability_score,
            "created_at": now,
        }
        for s in sources
    ]

    supabase.table("web_sources").insert(rows).execute()


def get_retrieved_paper(paper_id: str) -> dict | None:
    """Fetch a single retrieved paper by ID."""
    result = supabase.table("retrieved_papers").select("*").eq("id", paper_id).execute()
    if result.data:
        return result.data[0]
    return None


def write_parsed_paper(
    retrieved_paper_id: str,
    title: str,
    authors: list[str],
    abstract: str,
    sections: list[dict],
    references: list[str],
    figures: list[dict],
    full_text: str,
    parser_version: int | None = None,
) -> None:
    """Store parsed paper content in the database.

    parser_version (migration 009) marks the row as reusable by the parse cache. If the column does not exist yet the
    row is stored without it, so a missing migration costs the cache, not the parse."""
    fields = {
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "sections": sections,
        "cited_references": references,
        "figures": figures,
        "full_text": full_text,
    }
    if parser_version is not None:
        fields["parser_version"] = parser_version

    try:
        _upsert_parsed(retrieved_paper_id, fields)
    except Exception as e:
        if "parser_version" not in fields or "parser_version" not in str(e):
            raise
        logger.warning("parsed_papers.parser_version is missing - run db/migrations/009; stored without it (no caching)")
        fields.pop("parser_version")
        _upsert_parsed(retrieved_paper_id, fields)


def _upsert_parsed(retrieved_paper_id: str, fields: dict) -> None:
    existing = supabase.table("parsed_papers").select("id").eq("retrieved_paper_id", retrieved_paper_id).execute()
    if existing.data:
        supabase.table("parsed_papers").update({**fields, "updated_at": _now_ist()})             .eq("retrieved_paper_id", retrieved_paper_id).execute()
    else:
        supabase.table("parsed_papers").insert({"retrieved_paper_id": retrieved_paper_id, **fields}).execute()


def _like_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def find_cached_parse(paper: dict, min_version: int, min_chars: int) -> dict | None:
    """An earlier parsed_papers row for the same paper (arXiv id, then DOI, then exact title) under any other
    retrieved_paper, produced by parser version >= min_version and holding at least min_chars of full text.
    Newest first. None when there is no usable row."""
    lookups = []
    arxiv = re.sub(r"v\d+$", "", (paper.get("arxiv_id") or "").strip())
    if arxiv:
        lookups.append(("arxiv_id", "like", f"{_like_escape(arxiv)}%"))
    doi = (paper.get("doi") or "").strip().lower()
    if doi:
        lookups.append(("doi", "ilike", _like_escape(doi)))
    title = (paper.get("title") or "").strip()
    if len(title) >= 20:
        lookups.append(("title", "eq", title))

    for column, op, value in lookups:
        query = supabase.table("retrieved_papers").select("id").neq("id", paper["id"])
        query = getattr(query, op)(column, value)
        ids = [r["id"] for r in query.limit(50).execute().data]
        if not ids:
            continue
        rows = (
            supabase.table("parsed_papers").select("*")
            .in_("retrieved_paper_id", ids).gte("parser_version", min_version)
            .order("created_at", desc=True).limit(5).execute().data
        )
        for row in rows:
            if len(row.get("full_text") or "") >= min_chars:
                return row
    return None


# ---------- Stage 3 (Summarizer) ----------

def get_papers_for_stage3(query_id: str, sub_question_id: str) -> list[dict]:
    """Relevance-filtered papers for one sub-question, with their parsed
    sections/full_text attached (empty if parsing failed), best combined_score first."""
    papers = (
        supabase.table("retrieved_papers")
        .select("id,title,abstract,combined_score,reliability_score")
        .eq("query_id", query_id)
        .eq("sub_question_id", sub_question_id)
        .execute()
        .data
    )
    if not papers:
        return []

    # sorted in Python: Postgres puts NULL scores first on DESC, which would
    # push unscored papers to the top
    papers.sort(key=lambda p: p.get("combined_score") or 0, reverse=True)

    parsed = (
        supabase.table("parsed_papers")
        .select("retrieved_paper_id,sections,full_text")
        .in_("retrieved_paper_id", [p["id"] for p in papers])
        .execute()
        .data
    )
    by_id = {r["retrieved_paper_id"]: r for r in parsed}

    for p in papers:
        r = by_id.get(p["id"], {})
        p["sections"] = r.get("sections") or []
        p["full_text"] = r.get("full_text") or ""
    return papers


def get_web_sources_for_stage3(sub_question_id: str) -> list[dict]:
    """Web sources for one sub-question, best reliability_score first."""
    rows = (
        supabase.table("web_sources")
        .select("id,title,url,snippet,reliability_score")
        .eq("sub_question_id", sub_question_id)
        .execute()
        .data
    )
    rows.sort(key=lambda r: r.get("reliability_score") or 0, reverse=True)
    return rows


def write_digests(rows: list[dict]) -> None:
    """Store per-source digests (findings with quote verification flags)."""
    if not rows:
        return
    now = _now_ist()
    for row in rows:
        row.setdefault("created_at", now)
    supabase.table("digests").insert(rows).execute()


def write_coverage(rows: list[dict]) -> None:
    """Store the per-sub-question coverage decision."""
    if not rows:
        return
    now = _now_ist()
    for row in rows:
        row.setdefault("created_at", now)
    supabase.table("coverage_results").insert(rows).execute()