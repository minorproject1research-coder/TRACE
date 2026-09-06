# apps/api/graph/nodes/web_search_node.py
import asyncio
from apps.api.graph.state import SharedResearchState
from apps.api.agents.stage2_retrieval import web_search_agent
from apps.api.services import db_service


def web_search_node(state: SharedResearchState) -> dict:
    """For each sub-question, it runs the Web Search Agent, collects the results, and writes them to Supabase."""

    all_web_sources = []

    for sq in state.task_plan.sub_questions:
        sources = asyncio.run(web_search_agent.search_all(sq.queries))

        for src in sources:
            src.sub_question_id = sq.id

        all_web_sources.extend(sources)

    # write in Supabase
    db_service.write_web_sources(all_web_sources)

    # return only the field this node updates —
    # Stage 3 (Summarizer) will read it from state.web_sources
    return {"web_sources": all_web_sources}