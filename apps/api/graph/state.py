from pydantic import BaseModel
from typing import Optional
from apps.api.models.source import Source
from apps.api.models.task_plan import TaskPlan


class SharedResearchState(BaseModel):
    raw_query: str
    query_id: Optional[str] = None      # chosen by the API so the run id is known before the planner writes the plan; None = generated
    task_plan: Optional[TaskPlan] = None
    web_sources: list[Source] = []
    paper_results: list[dict] = []
    digests: list[dict] = []
    coverage: dict = {}