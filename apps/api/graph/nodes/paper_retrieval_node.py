import asyncio
import logging

from apps.api.graph.state import SharedResearchState
from apps.api.agents.stage2_retrieval.paper_retrieval_agent import PaperRetrievalAgent
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
        else:
            sq.papers = result
            all_papers.extend(result)

    logger.info("Retrieved %d total papers across %d sub-questions",
                len(all_papers), len(state.task_plan.sub_questions))

    db_service.write_retrieved_papers(state.task_plan.query_id, all_papers)
    logger.info("Stored %d papers in database for query %s",
                len(all_papers), state.task_plan.query_id)

    return {"paper_results": all_papers}


async def _retrieve_for_subquestion(
    agent: PaperRetrievalAgent,
    sq,
) -> list[dict]:
    if not sq.queries:
        logger.warning("No query variants for sub-question '%s'", sq.main_topic)
        return []

    return await agent.retrieve(
        sub_question=sq.main_topic,
        query_variants=sq.queries,
    )