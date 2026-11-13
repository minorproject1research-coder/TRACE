import logging

from apps.api.graph.state import SharedResearchState
from apps.api.models.task_plan import TaskPlan
from apps.api.agents.stage1_planner import domain_anchor, question_generator, query_expansion
from apps.api.services import db_service, progress
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
    try:
        source = question_generator.plan_source(state.raw_query)
        if source == "plan-cache":
            progress.note(task_plan.query_id, "plan_cache", "The stored plan for this question was reused (PLAN_CACHE), so the planner model was not called", stage="planner", source=source)
        elif source == "groq-fallback":
            progress.note(task_plan.query_id, "plan_fallback", "The planner model was unreachable, so Groq wrote the plan", level="warn", stage="planner", source=source)
        extra = question_generator.plan_notes(state.raw_query)
        if extra and extra.get("added"):
            left = f" and left out {len(extra['dropped'])} background sub-question(s)" if extra.get("dropped") else ""
            progress.note(task_plan.query_id, "answer_subquestions", f"Added {len(extra['added'])} sub-question(s) the answer needs (when it fails, risks and figures){left}",
                          stage="planner", added=extra["added"], dropped=extra.get("dropped") or [])
    except Exception:
        logger.debug("plan note dropped", exc_info=True)
    try:
        from apps.api.agents.stage3_summarizer import warmup
        warmup.start_aspects(task_plan.query_id, task_plan.sub_questions)     # STAGE3_WARM_ASPECTS: Stage 3 will find the cached answers
    except Exception:
        logger.exception("aspect warm-up could not start; Stage 3 splits the aspects itself")
    logger.info("Saved task plan with ID: %s", task_plan.query_id)
    if config.factcheck_enabled():          # this run goes through the factcheck node, so Stage 3 may hand it sub-questions early
        from apps.api.graph.nodes import factcheck_node
        factcheck_node.expect(task_plan.query_id)

    return {"task_plan": task_plan}