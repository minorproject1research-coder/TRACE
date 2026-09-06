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