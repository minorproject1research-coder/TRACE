import logging

from apps.api.graph.state import SharedResearchState
from apps.api.models.task_plan import TaskPlan
from apps.api.agents.stage1_planner import question_generator, query_expansion
from apps.api.services import db_service

logger = logging.getLogger("apps.api.agents.stage1_planner")


def planner_node(state: SharedResearchState) -> dict:
    logger.info("Starting planner for query: %s", state.raw_query[:100])

    sub_questions = question_generator.generate(state.raw_query)
    logger.info("Generated %d sub-questions", len(sub_questions))

    for sq in sub_questions:
        # the planner already supplies search queries; only a sub-question left without any is expanded with the LLM
        if not sq.queries:
            logger.info("No planner queries for '%s'; expanding with query_expansion", sq.main_topic[:60])
            sq.queries = query_expansion.expand(sq.main_topic, sq.detail_questions)

    task_plan = TaskPlan(raw_query=state.raw_query, sub_questions=sub_questions)
    db_service.write_task_plan(task_plan)
    logger.info("Saved task plan with ID: %s", task_plan.query_id)

    return {"task_plan": task_plan}