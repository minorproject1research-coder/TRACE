import asyncio
import logging

from apps.api.graph.state import SharedResearchState
from apps.api.agents.stage2_retrieval.paper_retrieval_agent import PaperRetrievalAgent
from apps.api.agents.stage2_retrieval import relevance_filter, reliability_scorer
from apps.api.services import db_service

logger = logging.getLogger("apps.api.agents.stage2_retrieval")


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
    """Fetches the retrieved_paper IDs just saved for this query, then parses
    only those (full text/sections/figures via Docling + PDFFigures)."""
    if not papers:
        return

    result = db_service.supabase.table("retrieved_papers") \
        .select("id") \
        .eq("query_id", query_id) \
        .execute()

    paper_ids = [row["id"] for row in result.data]

    if not paper_ids:
        logger.warning("No saved paper IDs found to parse for query %s", query_id)
        return

    logger.info("Parsing %d relevant papers (Docling + PDFFigures)...", len(paper_ids))
    parsed = await agent.parse_papers(paper_ids=paper_ids)
    logger.info("Successfully parsed %d/%d papers", len(parsed), len(paper_ids))


async def _retrieve_for_subquestion(agent: PaperRetrievalAgent, sq) -> list[dict]:
    if not sq.queries:
        logger.warning("No query variants for sub-question '%s'", sq.main_topic)
        return []

    return await agent.retrieve(
        sub_question=sq.main_topic,
        query_variants=sq.queries,
    )