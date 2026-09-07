import json
import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

_url = os.environ["SUPABASE_URL"]
_key = os.environ["SUPABASE_SERVICE_KEY"]

supabase: Client = create_client(_url, _key)


def write_task_plan(plan) -> None:
    sub_q_rows, query_rows = plan.to_supabase_rows()

    supabase.table("research_queries").upsert({
        "id": plan.query_id,
        "raw_query": plan.raw_query,
    }).execute()

    if sub_q_rows:
        supabase.table("sub_questions").upsert(sub_q_rows).execute()

    if query_rows:
        supabase.table("queries").insert(query_rows).execute()


def write_retrieved_papers(query_id: str, papers: list[dict]) -> None:
    """Store retrieved papers in the database, linked to the research query."""
    if not papers:
        return

    rows = []
    for paper in papers:
        rows.append({
            "query_id": query_id,
            "sub_question_id": paper.get("sub_question_id"),
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
    linked to the sub-question that found them."""
    if not sources:
        return

    rows = [
        {
            "sub_question_id": s.sub_question_id,
            "url": s.url,
            "title": s.title,
            "snippet": s.snippet,
            "published_date": s.published_date,
            "provider": s.provider,
            "reliability_score": s.reliability_score,
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