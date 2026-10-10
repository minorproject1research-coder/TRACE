import json
import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

_url = os.environ["SUPABASE_URL"]
_key = os.environ["SUPABASE_SERVICE_KEY"]

supabase: Client = create_client(_url, _key)

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
) -> None:
    """Store parsed paper content in the database."""
    now = _now_ist()

    existing = supabase.table("parsed_papers").select("id").eq("retrieved_paper_id", retrieved_paper_id).execute()

    if existing.data:
        supabase.table("parsed_papers").update({
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "sections": sections,
            "cited_references": references,
            "figures": figures,
            "full_text": full_text,
            "updated_at": now,
        }).eq("retrieved_paper_id", retrieved_paper_id).execute()
    else:
        supabase.table("parsed_papers").insert({
            "retrieved_paper_id": retrieved_paper_id,
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "sections": sections,
            "cited_references": references,
            "figures": figures,
            "full_text": full_text,
        }).execute()


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