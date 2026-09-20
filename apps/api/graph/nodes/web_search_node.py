# apps/api/graph/nodes/web_search_node.py
import asyncio
from apps.api.graph.state import SharedResearchState
from apps.api.agents.stage2_retrieval import web_search_agent, reliability_scorer
from apps.api.services import db_service


def web_search_node(state: SharedResearchState) -> dict:
    all_web_sources = []

    for sq in state.task_plan.sub_questions:
        sources = asyncio.run(web_search_agent.search_all(sq.queries))

        for src in sources:
            src.sub_question_id = sq.id
            # query_id line removed — not needed for web_sources

        all_web_sources.extend(sources)

    all_web_sources = reliability_scorer.score_all(all_web_sources)

    db_service.write_web_sources(all_web_sources)

    return {"web_sources": all_web_sources}