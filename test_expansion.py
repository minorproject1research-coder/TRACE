from apps.api.agents.stage1_planner.query_expansion import expand

result = expand(
    main_topic="Impact of RAG on hallucination rates in LLMs",
    detail_questions=[
        "Does RAG reduce factual errors compared to standalone LLMs?",
        "What metrics are used to measure hallucination reduction?"
    ]
)
print(result)