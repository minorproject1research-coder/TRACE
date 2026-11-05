import logging
import os
import re
from typing import Any, List

from apps.api.services import llm_service
from apps.api.services.llm_service import squeezer_json
from apps.api.agents.stage3_summarizer import digest_cache
from apps.api.agents.stage3_summarizer.quote_verifier import verify_quote

logger = logging.getLogger("apps.api.agents.stage3_summarizer")

# --- Constants ---
VALID_STRENGTHS = {"full", "partial"}
# Sampling of the digest call. Defaults keep the old behaviour (temperature 0.1, no seed); DIGEST_TEMPERATURE=0 and DIGEST_SEED=<int>
# make repeated calls MORE alike but not identical on a hosted model - the digest cache (digest_cache.py) is what guarantees identical reruns.
DIGEST_TEMPERATURE = float(os.getenv("DIGEST_TEMPERATURE", "0.1"))
DIGEST_SEED = int(os.environ["DIGEST_SEED"]) if os.getenv("DIGEST_SEED", "").strip() else None


DIGEST_PROMPT = """You extract evidence from a research source for ONE research question.

Research question: {question}

Detail aspects (numbered 1..N):
{detail_aspects}

Source text, split into chunks:
{chunks}

Return ONLY JSON: {{"findings": [{{"claim": "...", "quote": "...", "chunk_id": 0, "stance": "supports|contradicts|neutral", "answers_details": [{{"detail": 1, "strength": "full"}}, {{"detail": 2, "strength": "partial"}}]}}]}}

Rules:
- At most 5 findings. Only findings that help answer the research question.
- "quote" must be copied WORD FOR WORD from the chunk named by chunk_id. Never paraphrase. Max 40 words.
- "claim" is one sentence in your own words saying what the quote shows.
- "stance": supports = evidence that the effect or claim in the question holds; contradicts = evidence that it does not hold; neutral = background or methods.
- "answers_details": list of objects {{"detail": <int>, "strength": "full"|"partial"}} for each aspect this claim DIRECTLY answers.
  - Tag an aspect only if the claim itself would be an acceptable one-sentence answer to it, or an essential part of one.
  - Use "full" ONLY when the claim answers the WHOLE aspect or a complete sub-question.
  - Use "partial" when the claim answers only ONE PART of an aspect, is generic, or only touches the topic.
  - Background, definitions of the topic, motivation, and tangential claims should get an EMPTY list.
  - An empty list is expected and correct for many findings.
  - Mentioning the topic or sharing vocabulary with the question is NOT enough.
  - A claim must NEVER be tagged as answering an aspect about a different subject than the one it is about (e.g. inference-time context versus training data).
- If nothing is relevant, return {{"findings": []}}.
"""


def _clean_topic(main_topic: str) -> str:
    """Strip leading 'What is' and trailing '?' from main topic."""
    t = main_topic.strip()
    t = re.sub(r"^what\s+is\s+", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\?$", "", t).strip()
    return t


def _parse_answers_details(raw: Any, n_details: int) -> List[dict]:
    """
    Validate and normalize answers_details.
    
    Accepts:
    - New format: list of {"detail": int, "strength": "full"|"partial"}
    - Legacy format: list of ints (treated as strength="partial")
    
    Returns list of {"detail": int, "strength": "full"|"partial"} with:
    - detail in 1..n_details
    - strength in {"full", "partial"} (defaults to "partial")
    - deduped by detail (first occurrence wins)
    - empty list on any malformed input
    """
    if not isinstance(raw, list):
        return []
    
    out = []
    seen_details = set()
    
    for item in raw:
        # Handle legacy int format
        if isinstance(item, int):
            detail = item
            strength = "partial"
        elif isinstance(item, dict):
            detail = item.get("detail")
            strength = item.get("strength", "partial")
            if not isinstance(detail, int):
                continue
            if strength not in VALID_STRENGTHS:
                strength = "partial"
        else:
            continue
        
        if not (1 <= detail <= n_details):
            continue
        if detail in seen_details:
            continue
        
        seen_details.add(detail)
        out.append({"detail": detail, "strength": strength})
    
    return out


def generate_digest(
    sub_question: str,
    selected: list[tuple[int, str]],
    *,
    detail_aspects: list[str] | None = None,
    main_topic: str | None = None,
    cache_scope: tuple[str, str] | None = None,
    strict: bool = False,
) -> list[dict]:
    """
    selected = [(chunk_id, chunk_text)].
    detail_aspects = flattened list of aspects (already split from detail questions).
    cache_scope = (sub_question_id, source_id): when given (and DIGEST_CACHE is on) the model's reply is cached and reused.
    strict = raise the model/JSON error instead of returning [] (the summarizer needs it to retry and to count digest_failures; an
    empty list from a failed call used to look like "the source has nothing relevant").
    Returns findings with answers_details tags.
    """
    n_details = len(detail_aspects) if detail_aspects else 0
    
    # Build detail aspects text for prompt
    detail_text = ""
    if detail_aspects:
        detail_lines = [f"{i+1}. {dq}" for i, dq in enumerate(detail_aspects)]
        detail_text = "\n".join(detail_lines)
    else:
        detail_text = "(none provided)"
    
    cleaned_topic = _clean_topic(main_topic) if main_topic else ""
    question_for_prompt = f"{cleaned_topic}: {sub_question}" if cleaned_topic else sub_question

    block = "\n\n".join(f"[chunk {i}]\n{t}" for i, t in selected)
    prompt = DIGEST_PROMPT.format(question=question_for_prompt, detail_aspects=detail_text, chunks=block)
    key = None
    data = None
    if cache_scope is not None and digest_cache.enabled():
        key = digest_cache.make_key(cache_scope, detail_aspects, llm_service.MODEL_NAME, DIGEST_PROMPT,
                                    f"t={DIGEST_TEMPERATURE}|seed={DIGEST_SEED}", prompt)
        data = digest_cache.get(key)
        if data is not None:
            logger.info("Digest cache hit for source %s", cache_scope[1])
    if data is None:
        try:
            data = squeezer_json(prompt, temperature=DIGEST_TEMPERATURE, seed=DIGEST_SEED)
        except Exception as e:
            logger.error("Digest generation failed: %s", e)
            if strict:
                raise
            return []                                   # a failed call is never cached
        if key is not None:
            digest_cache.put(key, data)

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
            "answers_details": _parse_answers_details(f.get("answers_details"), n_details),
        })
    return findings