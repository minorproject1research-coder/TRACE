# apps/api/models/source.py
from pydantic import BaseModel
from typing import Optional


class Source(BaseModel):
    url: str
    title: str = ""
    snippet: str = ""
    published_date: Optional[str] = None
    source_type: str = "web"
    provider: str = ""
    reliability_score: Optional[float] = None
    sub_question_id: Optional[str] = None