import logging

from apps.api.graph.state import SharedResearchState
from apps.api.models.task_plan import TaskPlan
from apps.api.agents.stage1_planner import domain_anchor, question_generator, query_expansion
from apps.api.services import db_service
from apps.api import config

logger = logging.getLogger("apps.api.agents.stage1_planner")


def planner_node(state: SharedResearchState) -> dict:
    logger.info("Starting planner for query: %s", state.raw_query[:100])
    if config.factcheck_enabled():          # the NLI model takes a while to load; let it load while retrieval and Stage 3 run
        from apps.api.agents.stage4_factcheck import common as stage4_common
        stage4_common.preload_nli()

    sub_questions = question_generator.generate(state.raw_query)
    logger.info("Generated %d sub-questions", len(sub_questions))

    for sq in sub_questions:
        # the planner already supplies search queries; only a sub-question left without any is expanded with the LLM
        if not sq.queries:
            logger.info("No planner queries for '%s'; expanding with query_expansion", sq.main_topic[:60])
            sq.queries = query_expansion.expand(sq.main_topic, sq.detail_questions)

    # keep the field of the original question in the searches (the planner's background queries are generic); no-op when off
    anchor = domain_anchor.generate(state.raw_query)
    if anchor.anchor:
        for sq in sub_questions:
            sq.queries = domain_anchor.apply_to_queries(sq.queries, anchor.anchor)

    plan_ids = {"query_id": state.query_id} if state.query_id else {}       # an id chosen by the API; otherwise TaskPlan generates one
    task_plan = TaskPlan(raw_query=state.raw_query, sub_questions=sub_questions,
                         domain_anchor=anchor.anchor, domain_context=anchor.context, **plan_ids)
    db_service.write_task_plan(task_plan)
    logger.info("Saved task plan with ID: %s", task_plan.query_id)

    return {"task_plan": task_plan}