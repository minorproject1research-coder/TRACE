import logging

from apps.api.models.task_plan import SubQuestion

logger = logging.getLogger(__name__)


def generate(raw_query: str) -> list[SubQuestion]:
    logger.info("Generating sub-questions for query: %s", raw_query[:100])
    return [
        SubQuestion(
            main_topic="Effect of RAG on hallucination rates",
            detail_questions=[
                "Does RAG reduce factual errors compared to standalone LLMs?",
                "What metrics measure hallucination reduction?",
            ],
        ),
        SubQuestion(
            main_topic="Limitations of RAG in reducing hallucinations",
            detail_questions=[
                "In what scenarios does RAG fail to prevent hallucination?",
            ],
        ),
    ]