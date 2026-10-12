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

STAGE3_MIN_FULL_TEXT_CHARS = 3000      # a paper counts as having full text above this many parsed characters


def get_papers_for_stage3(query_id: str, sub_question_id: str) -> list[dict]:
    """Relevance-filtered papers for one sub-question with their parsed sections / full_text attached.

    Papers with usable parsed text come first (best combined_score first within each group), then abstract-only papers:
    a digest built from one abstract is much thinner evidence than one built from the paper, so the limited number of
    Stage 3 slots must not go to unparsed papers while parsed ones are left over. Each paper gets `has_full_text`."""
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
        p["has_full_text"] = len(p["full_text"]) >= STAGE3_MIN_FULL_TEXT_CHARS

    # sorted in Python: Postgres puts NULL scores first on DESC, which would push unscored papers to the top
    papers.sort(key=lambda p: (p["has_full_text"], p.get("combined_score") or 0), reverse=True)
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


OPTIONAL_DIGEST_COLUMNS = ("evidence_level",)                 # migration 010
OPTIONAL_COVERAGE_COLUMNS = ("full_text_source_count",)       # migration 010


def _insert_with_optional_columns(table: str, rows: list[dict], optional: tuple) -> None:
    """Insert rows; if the table lacks an optional column (migration not run yet), store them without it."""
    try:
        supabase.table(table).insert(rows).execute()
    except Exception as e:
        missing = [c for c in optional if c in str(e)]
        if not missing:
            raise
        logger.warning("%s.%s missing - run db/migrations/010; storing without it", table, ", ".join(missing))
        supabase.table(table).insert([{k: v for k, v in r.items() if k not in missing} for r in rows]).execute()


def write_digests(rows: list[dict]) -> None:
    """Store per-source digests (findings with quote verification flags)."""
    if not rows:
        return
    now = _now_ist()
    for row in rows:
        row.setdefault("created_at", now)
    _insert_with_optional_columns("digests", rows, OPTIONAL_DIGEST_COLUMNS)


def write_coverage(rows: list[dict]) -> None:
    """Store the per-sub-question coverage decision."""
    if not rows:
        return
    now = _now_ist()
    for row in rows:
        row.setdefault("created_at", now)
    _insert_with_optional_columns("coverage_results", rows, OPTIONAL_COVERAGE_COLUMNS)


# ---------- PDF download failures (negative cache, migration 011) ----------

_pdf_failures_unavailable = False                 # the table is missing: fall back to memory for this process
_pdf_failures_memory: dict[str, dict] = {}


def paper_key(paper: dict) -> str:
    """Identity of a paper across queries: arXiv id, else DOI, else normalised title (same key as the parse cache)."""
    arxiv = re.sub(r"v\d+$", "", (paper.get("arxiv_id") or "").strip())
    if arxiv:
        return f"arxiv:{arxiv}"
    doi = (paper.get("doi") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    return "title:" + re.sub(r"[^a-z0-9]+", " ", (paper.get("title") or "").lower()).strip()


def _pdf_failures_missing(e: Exception) -> bool:
    global _pdf_failures_unavailable
    if "pdf_failures" in str(e):
        if not _pdf_failures_unavailable:
            logger.warning("table pdf_failures is missing - run db/migrations/011; PDF failures are remembered for this run only")
        _pdf_failures_unavailable = True
        return True
    return False


def get_pdf_failures(keys: list[str], max_age_days: float, min_fetcher_version: int) -> dict[str, dict]:
    """Recorded PDF failures for these paper keys: seen within max_age_days and from a download logic at least as new as
    min_fetcher_version. {key: row}."""
    if not keys or max_age_days <= 0:
        return {}
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    found = {k: v for k, v in _pdf_failures_memory.items()
             if k in keys and v["last_seen"] >= cutoff and v["fetcher_version"] >= min_fetcher_version}
    if not _pdf_failures_unavailable:
        try:
            rows = (supabase.table("pdf_failures").select("*").in_("paper_key", list(keys))
                    .gte("fetcher_version", min_fetcher_version).gte("last_seen", cutoff.isoformat()).execute().data)
            for r in rows:
                found.setdefault(r["paper_key"], r)
        except Exception as e:
            if not _pdf_failures_missing(e):
                logger.warning("pdf_failures lookup failed: %s", str(e)[:150])
    return found


def record_pdf_failure(key: str, title: str, doi: str | None, error_class: str, error_detail: str, fetcher_version: int) -> None:
    now = datetime.now(timezone.utc)
    previous = _pdf_failures_memory.get(key, {})
    _pdf_failures_memory[key] = {"paper_key": key, "error_class": error_class, "last_seen": now, "fetcher_version": fetcher_version,
                                 "fail_count": previous.get("fail_count", 0) + 1}
    if _pdf_failures_unavailable:
        return
    try:
        existing = supabase.table("pdf_failures").select("fail_count,first_seen").eq("paper_key", key).execute().data
        supabase.table("pdf_failures").upsert({
            "paper_key": key, "title": (title or "")[:300], "doi": doi, "error_class": error_class, "error_detail": error_detail[:300],
            "fail_count": (existing[0]["fail_count"] + 1) if existing else 1, "fetcher_version": fetcher_version,
            "first_seen": existing[0]["first_seen"] if existing else now.isoformat(), "last_seen": now.isoformat(),
        }).execute()
    except Exception as e:
        if not _pdf_failures_missing(e):
            logger.warning("could not record a PDF failure: %s", str(e)[:150])


def clear_pdf_failure(key: str) -> None:
    """A paper that parsed fine is no longer a known failure."""
    _pdf_failures_memory.pop(key, None)
    if _pdf_failures_unavailable:
        return
    try:
        supabase.table("pdf_failures").delete().eq("paper_key", key).execute()
    except Exception as e:
        _pdf_failures_missing(e)
