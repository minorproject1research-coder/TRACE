import asyncio
from apps.api.agents.stage2_retrieval.web_search_agent import search_all


async def main():
    results = await search_all([
        "RAG impact on LLM hallucination rates",
        "retrieval augmented generation factual accuracy",
    ])
    for r in results:
        print(f"[{r.provider}] {r.title} — {r.url}")
    print(f"\nTotal unique sources: {len(results)}")


asyncio.run(main())