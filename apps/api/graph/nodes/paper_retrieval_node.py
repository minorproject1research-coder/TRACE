import asyncio
import logging
import os

from apps.api.graph.state import SharedResearchState
from apps.api.agents.stage2_retrieval.paper_retrieval_agent import PaperRetrievalAgent
from apps.api.agents.stage2_retrieval import relevance_filter, reliability_scorer
from apps.api.services import db_service

logger = logging.getLogger("apps.api.agents.stage2_retrieval")

# How many papers per sub-question are parsed (best combined_score first). 0 = parse all kept papers.
PARSE_TOP_N = max(0, int(os.getenv("PARSE_TOP_N_PER_SUBQUESTION", "5")))
# A sub-question may try up to this many times N papers to reach N with usable text.
PARSE_MAX_ATTEMPTS_FACTOR = max(1, int(os.getenv("PARSE_MAX_ATTEMPTS_FACTOR", "2")))
# A parse counts as usable full text above this many characters.
MIN_USABLE_TEXT_CHARS = 3000


def paper_retrieval_node(state: SharedResearchState) -> dict:
    agent = PaperRetrievalAgent(max_results_per_query=10)

    async def _retrieve_all():
        tasks = []
        for sq in state.task_plan.sub_questions:
            tasks.append(_retrieve_for_subquestion(agent, sq))
        return await asyncio.gather(*tasks, return_exceptions=True)

    results = asyncio.run(_retrieve_all())

    all_papers: list[dict] = []
    for sq, result in zip(state.task_plan.sub_questions, results):
        if isinstance(result, Exception):
            logger.error("Retrieval failed for sub-question '%s': %s", sq.main_topic, result)
            sq.papers = []
            continue

        for paper in result:
            paper["sub_question_id"] = sq.id

        # relevance filter — only keeps papers relevant to this sub-question
        relevant_papers = relevance_filter.filter_relevant(sq.main_topic, result)

        sq.papers = relevant_papers
        all_papers.extend(relevant_papers)

    # reliability scoring
    all_papers = reliability_scorer.score_all(all_papers)

    # combine relevance + reliability into one ranking score
    all_papers = [relevance_filter.compute_combined_score(p) for p in all_papers]

    logger.info("Retrieved %d relevant papers across %d sub-questions",
                len(all_papers), len(state.task_plan.sub_questions))

    db_service.write_retrieved_papers(state.task_plan.query_id, all_papers)
    logger.info("Stored %d papers in database for query %s",
                len(all_papers), state.task_plan.query_id)

    # NEW: parse full text/sections/figures — only for the relevance-filtered papers just saved
    asyncio.run(_parse_relevant_papers(agent, state.task_plan.query_id, all_papers))

    return {"paper_results": all_papers}


async def _parse_relevant_papers(agent: PaperRetrievalAgent, query_id: str, papers: list[dict]):
    """Parses (full text/sections/figures via Docling + PDFFigures) the best papers of each sub-question only:
    the top PARSE_TOP_N_PER_SUBQUESTION by combined_score. Stage 3 reads at most a few papers per sub-question, so
    parsing everything wasted most of the run. A paper that yields no usable text is replaced by the next one in
    rank, up to PARSE_MAX_ATTEMPTS_FACTOR x N attempts per sub-question. 0 for N = parse everything."""
    if not papers:
        return

    rows = db_service.supabase.table("retrieved_papers") \
        .select("id,sub_question_id,title,combined_score") \
        .eq("query_id", query_id) \
        .execute().data

    if not rows:
        logger.warning("No saved paper IDs found to parse for query %s", query_id)
        return

    by_sq: dict[str, list[dict]] = {}
    for row in sorted(rows, key=lambda r: r.get("combined_score") or 0, reverse=True):
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

    logger.info("Parsing done: %d usable full texts out of %d papers attempted (%d saved in total)",
                total_usable, total_attempted, len(rows))


async def _retrieve_for_subquestion(agent: PaperRetrievalAgent, sq) -> list[dict]:
    if not sq.queries:
        logger.warning("No query variants for sub-question '%s'", sq.main_topic)
        return []

    return await agent.retrieve(
        sub_question=sq.main_topic,
        query_variants=sq.queries,
    )