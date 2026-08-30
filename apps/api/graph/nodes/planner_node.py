from apps.api.graph.state import SharedResearchState
from apps.api.models.task_plan import TaskPlan
from apps.api.agents.stage1_planner import question_generator, query_expansion
from apps.api.services import db_service


def planner_node(state: SharedResearchState) -> SharedResearchState:
    sub_questions = question_generator.generate(state.raw_query)

    for sq in sub_questions:
        sq.queries = query_expansion.expand(sq.main_topic, sq.detail_questions)

    task_plan = TaskPlan(raw_query=state.raw_query, sub_questions=sub_questions)
    db_service.write_task_plan(task_plan)

    state.task_plan = task_plan
    return state