import asyncio
import logging
import os

from apps.api.graph.state import SharedResearchState
from apps.api.agents.stage2_retrieval.paper_retrieval_agent import DOWNLOADER_VERSION, PDF_FAILURE_TTL_DAYS, PaperRetrievalAgent
from apps.api.agents.stage2_retrieval import relevance_filter, reliability_scorer
from apps.api.services import db_service, progress

logger = logging.getLogger("apps.api.agents.stage2_retrieval")

# How many papers per sub-question are parsed (best combined_score first). 0 = parse all kept papers.
PARSE_TOP_N = max(0, int(os.getenv("PARSE_TOP_N_PER_SUBQUESTION", "5")))
# Try papers that have a direct PDF source (an arXiv id or an open-access PDF link) before papers that only have a DOI. DOI-only
# papers (most Scopus and many OpenAlex results) usually end at a paywalled landing page or HTTP 403, and every such miss costs
# a download attempt plus the Unpaywall / Playwright fallbacks. Within each group the order is still by combined_score.
PARSE_PREFER_DIRECT_PDF = os.getenv("PARSE_PREFER_DIRECT_PDF", "true").lower() not in ("0", "false", "no")
# A sub-question may try up to this many times N papers to reach N with usable text.
PARSE_MAX_ATTEMPTS_FACTOR = max(1, int(os.getenv("PARSE_MAX_ATTEMPTS_FACTOR", "2")))
# A parse counts as usable full text above this many characters.
MIN_USABLE_TEXT_CHARS = 3000


def paper_retrieval_node(state: SharedResearchState) -> dict:
    qid = state.task_plan.query_id
    sub_questions = state.task_plan.sub_questions
    progress.report(qid, "papers", "branch", "running", "Paper retrieval started")
    agent = PaperRetrievalAgent(max_results_per_query=10)

    async def _retrieve_all():
        tasks = []
        for sq in sub_questions:
            tasks.append(_retrieve_for_subquestion(agent, sq))
        return await asyncio.gather(*tasks, return_exceptions=True)

    progress.report(qid, "papers", "search", "running", "Searching OpenAlex, Scopus and arXiv",
                    subQuestions=len(sub_questions), queries=sum(len(sq.queries or []) for sq in sub_questions))
    results = asyncio.run(_retrieve_all())
    candidates = sum(len(r) for r in results if not isinstance(r, Exception))
    progress.report(qid, "papers", "search", "completed", f"Found {candidates} candidate papers", candidates=candidates)

    progress.report(qid, "papers", "relevance_filter", "running", "Judging relevance (embedding shortlist, then the LLM judge)",
                    candidates=candidates, done=0, total=len(sub_questions))
    totals = {"candidates": 0, "shortlisted": 0, "judged": 0, "passed": 0, "judgeUnavailable": 0}
    judge_backend = None
    all_papers: list[dict] = []
    for done, (sq, result) in enumerate(zip(sub_questions, results), start=1):
        if isinstance(result, Exception):
            logger.error("Retrieval failed for sub-question '%s': %s", sq.main_topic, result)
            sq.papers = []
            continue

        for paper in result:
            paper["sub_question_id"] = sq.id

        # relevance filter — only keeps papers relevant to this sub-question
        stats: dict = {}
        relevant_papers = relevance_filter.filter_relevant(sq.main_topic, result, anchor=state.task_plan.domain_anchor,
                                                           context=state.task_plan.domain_context, stats=stats)
        for k in totals:
            totals[k] += stats.get(k, 0)
        judge_backend = stats.get("backend", judge_backend)
        progress.report(qid, "papers", "relevance_filter", "running", f"Judged sub-question {done} of {len(sub_questions)}",
                        done=done, total=len(sub_questions), backend=judge_backend, **totals)

        sq.papers = relevant_papers
        all_papers.extend(relevant_papers)
    progress.report(qid, "papers", "relevance_filter", "completed",
                    f"{totals['passed']} of {candidates} candidates passed ({totals['judged']} judge calls)", backend=judge_backend, **totals)

    # citation counts only for the papers that survived the filter (they feed the reliability score)
    progress.report(qid, "papers", "citations", "running", "Fetching citation counts for the papers that passed", papers=len(all_papers))
    kept = asyncio.run(agent.enrich_papers(all_papers))
    if len(kept) != len(all_papers):
        kept_ids = {id(p) for p in kept}
        for sq in sub_questions:
            sq.papers = [p for p in sq.papers if id(p) in kept_ids]
        all_papers = kept
    progress.report(qid, "papers", "citations", "completed", f"{len(all_papers)} papers kept", kept=len(all_papers))

    # reliability scoring
    progress.report(qid, "papers", "scoring", "running", "Scoring reliability and ranking", papers=len(all_papers))
    all_papers = reliability_scorer.score_all(all_papers)

    # combine relevance + reliability into one ranking score
    all_papers = [relevance_filter.compute_combined_score(p) for p in all_papers]
    progress.report(qid, "papers", "scoring", "completed", f"Scored {len(all_papers)} papers", scored=len(all_papers))

    logger.info("Retrieved %d relevant papers across %d sub-questions",
                len(all_papers), len(sub_questions))

    progress.report(qid, "papers", "store", "running", "Saving the papers", papers=len(all_papers))
    db_service.write_retrieved_papers(state.task_plan.query_id, all_papers)
    logger.info("Stored %d papers in database for query %s",
                len(all_papers), state.task_plan.query_id)
    progress.report(qid, "papers", "store", "completed", f"Saved {len(all_papers)} papers", stored=len(all_papers))

    # NEW: parse full text/sections/figures — only for the relevance-filtered papers just saved
    asyncio.run(_parse_relevant_papers(agent, state.task_plan.query_id, all_papers))

    return {"paper_results": all_papers}


def _parse_priority(row: dict, failed_keys: frozenset = frozenset()) -> tuple:
    """Sort key (descending): papers whose PDF is not a known failure first, then papers with a direct PDF source (if enabled),
    then by combined_score. A known failure is still in the queue, behind everything else, and is skipped cheaply by the agent."""
    direct = bool(row.get("arxiv_id") or row.get("pdf_url")) if PARSE_PREFER_DIRECT_PDF else False
    return (db_service.paper_key(row) not in failed_keys, direct, row.get("combined_score") or 0)


async def _parse_relevant_papers(agent: PaperRetrievalAgent, query_id: str, papers: list[dict]):
    """Parses (full text/sections/figures via Docling + PDFFigures) the best papers of each sub-question only:
    the top PARSE_TOP_N_PER_SUBQUESTION by combined_score. Stage 3 reads at most a few papers per sub-question, so
    parsing everything wasted most of the run. A paper that yields no usable text is replaced by the next one in
    rank, up to PARSE_MAX_ATTEMPTS_FACTOR x N attempts per sub-question. 0 for N = parse everything."""
    if not papers:
        progress.report(query_id, "papers", "parsing", "skipped", "No papers to parse")
        return

    rows = db_service.supabase.table("retrieved_papers") \
        .select("id,sub_question_id,title,combined_score,arxiv_id,pdf_url,doi") \
        .eq("query_id", query_id) \
        .execute().data

    if not rows:
        logger.warning("No saved paper IDs found to parse for query %s", query_id)
        progress.report(query_id, "papers", "parsing", "skipped", "No saved papers to parse")
        return

    by_sq: dict[str, list[dict]] = {}
    failed_keys = frozenset(db_service.get_pdf_failures([db_service.paper_key(r) for r in rows], PDF_FAILURE_TTL_DAYS, DOWNLOADER_VERSION))
    if failed_keys:
        logger.info("%d of the %d kept papers have a recorded PDF failure; they are tried last", len(failed_keys), len(rows))
    for row in sorted(rows, key=lambda r: _parse_priority(r, failed_keys), reverse=True):
        by_sq.setdefault(row["sub_question_id"], []).append(row)

    queues = {sq: list(rs) for sq, rs in by_sq.items()}
    target = {sq: len(rs) if PARSE_TOP_N <= 0 else min(PARSE_TOP_N, len(rs)) for sq, rs in by_sq.items()}
    max_attempts = {sq: len(rs) if PARSE_TOP_N <= 0 else min(len(rs), PARSE_TOP_N * PARSE_MAX_ATTEMPTS_FACTOR)
                    for sq, rs in by_sq.items()}
    attempted = {sq: 0 for sq in by_sq}
    usable = {sq: 0 for sq in by_sq}
    total_attempted = total_usable = 0

    logger.info("Parsing the top %s papers per sub-question by combined_score (%d saved across %d sub-questions)...",
                PARSE_TOP_N or "all", len(rows), len(by_sq))
    total_target = sum(target.values())
    progress.report(query_id, "papers", "parsing", "running", f"Parsing the best {total_target} papers (PDF to text)",
                    target=total_target, attempted=0, usable=0, papers=len(rows))
    while True:
        batch: list[tuple[str, dict]] = []
        for sq, queue in queues.items():
            need = target[sq] - usable[sq]
            room = max_attempts[sq] - attempted[sq]
            take = min(need, room, len(queue))
            for _ in range(take):
                batch.append((sq, queue.pop(0)))
            attempted[sq] += max(take, 0)
        if not batch:
            break

        parsed = await agent.parse_papers(paper_ids=[r["id"] for _, r in batch])
        text_by_id = {p.retrieved_paper_id: len(p.full_text or "") for p in parsed}
        for sq, row in batch:
            total_attempted += 1
            if text_by_id.get(row["id"], 0) >= MIN_USABLE_TEXT_CHARS:
                usable[sq] += 1
                total_usable += 1
            else:
                logger.info("No usable full text for '%s' — trying the next paper of that sub-question if any",
                            row["title"][:60])
        progress.report(query_id, "papers", "parsing", "running", f"Parsed {total_usable} of {total_target} papers",
                        target=total_target, attempted=total_attempted, usable=total_usable)

    logger.info("Parsing done: %d usable full texts out of %d papers attempted (%d saved in total)",
                total_usable, total_attempted, len(rows))
    progress.report(query_id, "papers", "parsing", "completed", f"{total_usable} of {total_target} papers parsed",
                    target=total_target, attempted=total_attempted, usable=total_usable)


async def _retrieve_for_subquestion(agent: PaperRetrievalAgent, sq) -> list[dict]:
    if not sq.queries:
        logger.warning("No query variants for sub-question '%s'", sq.main_topic)
        return []

    return await agent.retrieve(
        sub_question=sq.main_topic,
        query_variants=sq.queries,
        enrich=False,       # citation counts are fetched after the relevance filter (agent.enrich_papers)
    )