import logging
import os

from apps.api.models.task_plan import SubQuestion
from apps.api.services import trace_llm_service
from apps.api.services.trace_llm_service import TraceLLMError

logger = logging.getLogger(__name__)

# Caps keep retrieval time bounded: every search query fans out to arXiv, Semantic Scholar, IEEE, OpenAlex and the web.
MAX_SUBQUESTIONS = int(os.getenv("MAX_SUBQUESTIONS", "5"))
MAX_QUERIES_PER_SUBQUESTION = int(os.getenv("MAX_QUERIES_PER_SUBQUESTION", "3"))
# groq: if the model server is unreachable, decompose with the Groq model instead; none: raise the error
LLM_FALLBACK = os.getenv("TRACE_LLM_FALLBACK", "groq").lower()


def generate(raw_query: str) -> list[SubQuestion]:
    """Break a research question into sub-questions using the fine-tuned planner (POST /decompose).

    The planner also returns search queries, as one flat list for the whole question. They are split across the
    sub-questions here (sq.queries); any sub-question left without a query is filled by query_expansion afterwards."""
    logger.info("Generating sub-questions for query: %s", raw_query[:100])
    try:
        plan = trace_llm_service.decompose(raw_query)
        source = "planner"
    except TraceLLMError as e:
        if LLM_FALLBACK != "groq":
            raise
        logger.warning("Planner server unavailable (%s); falling back to Groq decomposition", e)
        plan = _groq_decompose(raw_query)
        source = "groq-fallback"

    sub_questions = _build_sub_questions(plan)
    _assign_queries(sub_questions, plan["search_queries"])
    logger.info("Planner (%s): %d sub-questions, %d search queries -> %s", source, len(sub_questions),
                len(plan["search_queries"]), [len(sq.queries) for sq in sub_questions])
    return sub_questions


def _build_sub_questions(plan: dict) -> list[SubQuestion]:
    seen, result = set(), []
    for s in plan["sub_questions"]:
        key = " ".join(s["topic"].lower().split())
        if key in seen:                                 # the planner occasionally repeats a topic
            continue
        seen.add(key)
        result.append(SubQuestion(main_topic=s["topic"], detail_questions=s["details"] or [s["topic"]]))
    if len(result) > MAX_SUBQUESTIONS:
        logger.warning("Planner returned %d sub-questions; keeping the first %d", len(result), MAX_SUBQUESTIONS)
        result = result[:MAX_SUBQUESTIONS]
    return result


def _assign_queries(sub_questions: list[SubQuestion], queries: list[str]) -> None:
    """Give each search query to the sub-question it matches best (embedding similarity of the query against the
    sub-question's topic and detail questions), keeping at most MAX_QUERIES_PER_SUBQUESTION per sub-question."""
    queries = list(dict.fromkeys(queries))              # drop exact duplicates, keep order
    if not queries or not sub_questions:
        return
    from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder   # shared bge model, loaded once

    model = get_embedder()
    sq_vecs = model.encode([f"{sq.main_topic} " + " ".join(sq.detail_questions) for sq in sub_questions],
                           normalize_embeddings=True)
    q_vecs = model.encode(queries, normalize_embeddings=True)
    sims = q_vecs @ sq_vecs.T                           # (queries x sub-questions)

    buckets: list[list[tuple[float, str]]] = [[] for _ in sub_questions]
    for i, query in enumerate(queries):
        best = int(sims[i].argmax())
        buckets[best].append((float(sims[i, best]), query))
    for sq, bucket in zip(sub_questions, buckets):
        sq.queries = [q for _, q in sorted(bucket, reverse=True)[:MAX_QUERIES_PER_SUBQUESTION]]


GROQ_DECOMPOSE_PROMPT = """You are a research planner. Break the research question into 2-5 sub-questions that together cover it
(background concepts first, then the core question), each with 1-3 detail questions, and write short search-ready queries.

Research question: {question}

Return ONLY a JSON object in exactly this format:
{{"sub_questions": [{{"topic": "...", "details": ["...", "..."]}}], "search_queries": ["...", "..."]}}
"""


def _groq_decompose(question: str) -> dict:
    """Fallback with the same output schema as the planner. Used only when the model server is unreachable."""
    from groq import Groq
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b", temperature=0.3,
        messages=[{"role": "user", "content": GROQ_DECOMPOSE_PROMPT.format(question=question)}],
    )
    raw = response.choices[0].message.content.strip()
    obj = trace_llm_service.extract_json_from_output(raw.replace("```json", "").replace("```", ""))
    try:
        return trace_llm_service._normalize_plan(obj)
    except TraceLLMError as e:
        raise TraceLLMError(f"Groq fallback also failed: {e}") from e
