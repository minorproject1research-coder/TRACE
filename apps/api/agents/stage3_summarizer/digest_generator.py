import logging
from apps.api.services.llm_service import squeezer_json
from apps.api.agents.stage3_summarizer.quote_verifier import verify_quote

logger = logging.getLogger("apps.api.agents.stage3_summarizer")

DIGEST_PROMPT = """You extract evidence from a research source for ONE research question.

Research question: {question}

Source text, split into chunks:
{chunks}

Return ONLY JSON: {{"findings": [{{"claim": "...", "quote": "...", "chunk_id": 0, "stance": "supports|contradicts|neutral"}}]}}

Rules:
- At most 5 findings. Only findings that help answer the research question.
- "quote" must be copied WORD FOR WORD from the chunk named by chunk_id. Never paraphrase. Max 40 words.
- "claim" is one sentence in your own words saying what the quote shows.
- "stance": supports = evidence that the effect or claim in the question holds; contradicts = evidence that it does not hold; neutral = background or methods.
- If nothing is relevant, return {{"findings": []}}.
"""


def generate_digest(sub_question: str, selected: list[tuple[int, str]]) -> list[dict]:
    """selected = [(chunk_id, chunk_text)]. Returns findings, each flagged verified or not."""
    block = "\n\n".join(f"[chunk {i}]\n{t}" for i, t in selected)
    try:
        data = squeezer_json(DIGEST_PROMPT.format(question=sub_question, chunks=block))
    except Exception as e:
        logger.error("Digest generation failed: %s", e)
        return []

    texts = [t for _, t in selected]
    findings = []
    for f in (data.get("findings") or [])[:5]:
        quote = (f.get("quote") or "").strip()
        findings.append({
            "claim": f.get("claim", ""),
            "quote": quote,
            "chunk_id": f.get("chunk_id"),
            "stance": f.get("stance", "neutral"),
            "verified": verify_quote(quote, texts),
        })
    return findings