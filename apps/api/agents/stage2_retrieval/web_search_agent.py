# apps/api/agents/stage2_retrieval/web_search_agent.py
import os
import asyncio
import logging
import httpx
from dotenv import load_dotenv
from apps.api.agents.stage2_retrieval.key_pool import KeyPool
from apps.api.models.source import Source

load_dotenv()

logger = logging.getLogger("apps.api.agents.stage2_retrieval")

tavily_pool = KeyPool(os.environ.get("TAVILY_API_KEYS", "").split(","))
exa_pool = KeyPool(os.environ.get("EXA_API_KEYS", "").split(","))
parallel_pool = KeyPool(os.environ.get("PARALLEL_API_KEYS", "").split(","))


async def _call_with_key_rotation(pool: KeyPool, call_fn, provider_name: str, *args, max_attempts: int = 3):
    """Try one key; if it is rate-limited, move to the next key in the pool.
    It will retry up to max_attempts or until all provider keys have been tried."""
    for attempt in range(max_attempts):
        key = pool.get_key()
        if not key:
            logger.warning("%s: all keys exhausted/cooling down", provider_name)
            return []  # All keys for this provider are currently on cooldown.
        result = await call_fn(key, *args)
        if result is not None:
            return result
        logger.warning("%s: key rate-limited, rotating (attempt %d/%d)", provider_name, attempt + 1, max_attempts)
        pool.mark_rate_limited(key)
    return []


async def _tavily_call(key: str, client: httpx.AsyncClient, query: str):
    try:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={"api_key": key, "query": query, "max_results": 5},
            timeout=15,
        )
        if resp.status_code == 429:
            return None  # rate-limit signal -> triggers key rotation
        resp.raise_for_status()
        data = resp.json()
        return [
            Source(
                url=r["url"], title=r.get("title", ""), snippet=r.get("content", ""),
                published_date=r.get("published_date"), source_type="web", provider="tavily",
            )
            for r in data.get("results", [])
        ]
    except Exception as e:
        logger.error("Tavily request failed: %s", e)
        return []


async def _exa_call(key: str, client: httpx.AsyncClient, query: str):
    try:
        resp = await client.post(
            "https://api.exa.ai/search",
            headers={"x-api-key": key},
            json={"query": query, "numResults": 5, "type": "auto"},
            timeout=15,
        )
        if resp.status_code == 429:
            return None
        resp.raise_for_status()
        data = resp.json()
        return [
            Source(
                url=r["url"], title=r.get("title", ""), snippet=(r.get("text") or "")[:500],
                published_date=r.get("publishedDate"), source_type="web", provider="exa",
            )
            for r in data.get("results", [])
        ]
    except Exception as e:
        logger.error("Exa request failed: %s", e)
        return []


async def _parallel_call(key: str, client: httpx.AsyncClient, query: str):
    try:
        resp = await client.post(
            "https://api.parallel.ai/v1beta/search",
            headers={"x-api-key": key, "Content-Type": "application/json"},
            json={"objective": query, "search_queries": [query]},
            timeout=15,
        )
        if resp.status_code == 429:
            return None
        resp.raise_for_status()
        data = resp.json()
        return [
            Source(
                url=r.get("url", ""), title=r.get("title", ""),
                snippet=(r.get("excerpts") or [""])[0][:500] if r.get("excerpts") else "",
                published_date=None, source_type="web", provider="parallel",
            )
            for r in data.get("results", [])
        ]
    except Exception as e:
        logger.error("Parallel AI request failed: %s", e)
        return []


async def _search_one_query(client: httpx.AsyncClient, query: str) -> list[Source]:
    """Tavily is fully tried first (up to 3 keys). Only if it returns no results do we try Exa.
    If Exa also returns no results, we then try Parallel. This ensures that only one provider's credits are consumed at a time
    """
    logger.info("Searching web for query: %s", query[:100])

    result = await _call_with_key_rotation(tavily_pool, _tavily_call, "tavily", client, query)
    if result:
        logger.info("Tavily returned %d results for: %s", len(result), query[:60])
        return result

    result = await _call_with_key_rotation(exa_pool, _exa_call, "exa", client, query)
    if result:
        logger.info("Exa returned %d results for: %s", len(result), query[:60])
        return result

    result = await _call_with_key_rotation(parallel_pool, _parallel_call, "parallel", client, query)
    if result:
        logger.info("Parallel returned %d results for: %s", len(result), query[:60])
    else:
        logger.warning("No provider returned results for: %s", query[:60])
    return result


async def search_all(query_variants: list[str]) -> list[Source]:
    """"All query variants for a sub-question run in parallel.
    This is different from provider-level parallelism—it is variant-level parallelism."""
    logger.info("Starting web search for %d query variants", len(query_variants))

    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(
            *[_search_one_query(client, q) for q in query_variants]
        )

    seen = set()
    flat = []
    for batch in results:
        for src in batch:
            if src.url and src.url not in seen:
                seen.add(src.url)
                flat.append(src)

    logger.info("Web search complete: %d unique sources after deduplication", len(flat))
    return flat