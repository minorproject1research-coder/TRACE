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
    fact_claims: list = []              # Stage 4 (FACTCHECK=true): one row per checked claim
    fact_summary: dict = {}             # Stage 4: counts per sub-question id, or {"error": ...}
    written_report: dict = {}           # Stage 5 (STAGE5=true): the structured written report (also stored in the table written_reports)
    written_report_status: str = ""     # Stage 5: completed | completed_with_warnings | insufficient_evidence | failed ("" = Stage 5 did not run)