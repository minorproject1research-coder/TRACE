from pydantic import BaseModel, Field
import uuid


class SubQuestion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    main_topic: str
    detail_questions: list[str]
    queries: list[str] = Field(default_factory=list)


class TaskPlan(BaseModel):
    query_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    raw_query: str
    sub_questions: list[SubQuestion]

    def to_supabase_rows(self) -> tuple[list[dict], list[dict]]:
        sub_q_rows = []
        query_rows = []
        for sq in self.sub_questions:
            sub_q_rows.append({
                "id": sq.id,
                "query_id": self.query_id,
                "main_topic": sq.main_topic,
                "detail_questions": sq.detail_questions,
            })
            for q in sq.queries:
                query_rows.append({
                    "sub_question_id": sq.id,
                    "query_text": q,
                })
        return sub_q_rows, query_rows