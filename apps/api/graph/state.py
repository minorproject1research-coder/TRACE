from pydantic import BaseModel
from typing import Optional
from apps.api.models.source import Source
from apps.api.models.task_plan import TaskPlan


class SharedResearchState(BaseModel):
    raw_query: str
    task_plan: Optional[TaskPlan] = None
    web_sources: list[Source] = []
    paper_results: list[dict] = []