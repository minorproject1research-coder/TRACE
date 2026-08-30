from apps.api.models.task_plan import SubQuestion


def generate(raw_query: str) -> list[SubQuestion]:
    """TEMPORARY MOCK — replace with fine-tuned Qwen inference once LoRA training is complete."""
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