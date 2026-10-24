# apps/api/agents/stage3_summarizer/detail_aspects.py
"""
Split compound detail questions into distinct aspects for tagging and coverage.

One LLM call per distinct detail (cached). Used by the orchestrator to flatten
aspects for chunk selection and digest generation.
"""
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from apps.api.services.llm_service import squeezer_json

logger = logging.getLogger("apps.api.agents.stage3_summarizer.detail_aspects")

# Cache file for aspect splits (JSONL, one per line: key -> aspects)
ASPECT_CACHE_PATH = Path("reports/aspect_cache.json")


ASPECT_SPLIT_PROMPT = """Split the following detail question into distinct aspects ONLY if it explicitly asks for two or more separate things to be answered individually.

Detail question: {detail}

Subject/context: {topic}

Return ONLY JSON: {{"aspects": ["aspect 1", "aspect 2", ...]}}

Rules:
- Split ONLY when the question explicitly asks for distinct things to be answered separately.
  Examples:
  - "advantages and disadvantages of X" -> ["advantages of X", "disadvantages of X"]
  - "examples and benefits of X" -> ["examples of X", "benefits of X"]
  - "how X is defined and measured" -> ["how X is defined", "how X is measured"]
  - "risks and benefits" -> ["risks of X", "benefits of X"]
  - "causes and effects" -> ["causes of X", "effects of X"]
- Do NOT split when "and" or "or" joins parts of ONE concept or noun phrase:
  - "LoRA and full fine-tuning" -> ["LoRA and full fine-tuning"] (one concept)
  - "encoder-decoder architecture" -> ["encoder-decoder architecture"] (one concept)
  - "e.g. A, B, C" -> ["e.g. A, B, C"] (examples list)
  - "definition and properties" -> ["definition and properties"] (one concept with two words)
  - "impact on speed and memory" -> ["impact on speed and memory"] (single aspect: impact)
- Each aspect must be a self-contained question that includes the subject.
- Maximum 3 aspects.
- If no clear split, return the original as a single aspect.
"""


def _cache_key(sub_question_id: str, detail_text: str) -> str:
    """Generate a stable cache key from sub-question ID and detail text."""
    h = hashlib.sha256(f"{sub_question_id}|{detail_text}".encode()).hexdigest()[:16]
    return h


def _load_cache() -> Dict[str, List[str]]:
    """Load aspect cache from JSONL file."""
    cache = {}
    if ASPECT_CACHE_PATH.exists():
        try:
            with open(ASPECT_CACHE_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = json.loads(line)
                    cache[entry["key"]] = entry["aspects"]
        except Exception as e:
            logger.warning(f"Failed to load aspect cache: {e}")
    return cache


def _save_cache_entry(key: str, aspects: List[str]) -> None:
    """Append a single entry to the cache file."""
    ASPECT_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(ASPECT_CACHE_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "aspects": aspects}) + "\n")
    except Exception as e:
        logger.warning(f"Failed to write aspect cache: {e}")


def split_detail_aspects(
    detail_text: str,
    sub_question_id: str,
    main_topic: str,
) -> List[str]:
    """
    Split a detail question into aspects using the LLM, with caching.
    
    Args:
        detail_text: The detail question text to split.
        sub_question_id: The sub-question ID for cache keying.
        main_topic: The cleaned main topic (subject) for context.
    
    Returns:
        List of 1-3 aspect strings. Falls back to [detail_text] on any failure.
    """
    key = _cache_key(sub_question_id, detail_text)
    cache = _load_cache()
    
    if key in cache:
        logger.info(f"Aspect cache hit for detail: {detail_text[:60]}...")
        return cache[key]
    
    logger.info(f"Splitting detail into aspects: {detail_text[:80]}...")
    
    try:
        prompt = ASPECT_SPLIT_PROMPT.format(detail=detail_text, topic=main_topic)
        data = squeezer_json(prompt)
        aspects = data.get("aspects", [])
        
        # Validate: 1-3 non-empty strings
        if not isinstance(aspects, list) or not (1 <= len(aspects) <= 3):
            logger.warning(f"Aspect split returned invalid count ({len(aspects)}): {aspects}")
            return [detail_text]
        
        clean_aspects = []
        for a in aspects:
            if not isinstance(a, str):
                logger.warning(f"Aspect split returned non-string: {a}")
                return [detail_text]
            a = a.strip()
            if not a:
                logger.warning("Aspect split returned empty string")
                return [detail_text]
            clean_aspects.append(a)
        
        logger.info(f"Split detail into {len(clean_aspects)} aspects: {clean_aspects}")
        _save_cache_entry(key, clean_aspects)
        return clean_aspects
        
    except Exception as e:
        logger.error(f"Aspect split failed for '{detail_text[:60]}': {e}")
        return [detail_text]


def flatten_aspects(
    detail_questions: List[str],
    sub_question_id: str,
    main_topic: str,
) -> tuple[List[str], List[int]]:
    """
    Flatten all detail questions into a single list of aspects.
    
    Returns:
        (aspects_list, aspect_to_detail_map)
        - aspects_list: flattened list of all aspects
        - aspect_to_detail_map: for each aspect index, the original detail index (0-based)
    """
    all_aspects = []
    aspect_to_detail = []
    
    for detail_idx, detail in enumerate(detail_questions):
        aspects = split_detail_aspects(detail, sub_question_id, main_topic)
        for _ in aspects:
            aspect_to_detail.append(detail_idx)
        all_aspects.extend(aspects)
    
    return all_aspects, aspect_to_detail