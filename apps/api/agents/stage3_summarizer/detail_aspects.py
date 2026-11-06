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
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder
from apps.api.services.llm_service import squeezer_json
from apps.api.services.text_norm import normalized_words

logger = logging.getLogger("apps.api.agents.stage3_summarizer.detail_aspects")

# Cache file for aspect splits (JSONL, one per line: key -> aspects)
ASPECT_CACHE_PATH = Path("reports/aspect_cache.json")

# Near-duplicate aspect merging threshold
NEAR_DUP_ASPECT_SIM = float(os.getenv("NEAR_DUP_ASPECT_SIM", "0.92"))


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


MERGE_MODES = ("exact", "embedding", "off")
LEGACY_MERGE_MODE = "embedding"      # what every run before 2026-11-05 used; tools that rebuild the aspects of a stored run need it


def merge_mode() -> str:
    """ASPECT_MERGE: how aspects of one sub-question are de-duplicated.

    exact (default)  merge only identical aspects (same words once stop words and plurals are ignored) that came from the SAME detail question.
    embedding        the old rule: merge any two aspects whose bge cosine is >= NEAR_DUP_ASPECT_SIM. Lossy, see below.
    off              never merge.

    Why embedding is not the default: aspects of one sub-question share the topic words, so unrelated aspects score 0.85-0.99 and the merge
    removed questions the user asked ("defined" vs "measured" 0.96, "sources" vs "impacts" 0.97, "empirical results" vs "theoretical
    explanations" 0.98). It also made a whole detail question vanish from coverage when all its aspects were merged into another detail's.
    The word that differs does not help: "advantages"/"disadvantages" score higher than "motivation"/"goal" as embeddings."""
    mode = os.getenv("ASPECT_MERGE", "exact").strip().lower()
    return mode if mode in MERGE_MODES else "exact"


def run_merge_mode(coverage_row: Optional[Dict]) -> str:
    """The merge mode a stored run used (written into judge_stats by the summarizer); runs without the marker used the old embedding rule."""
    stats = (coverage_row or {}).get("judge_stats") or {}
    return stats.get("aspect_merge") if stats.get("aspect_merge") in MERGE_MODES else LEGACY_MERGE_MODE


_normalized = normalized_words      # the shared helper (apps/api/services/text_norm.py)


def _merge_near_duplicate_aspects(
    aspects: List[str],
    aspect_to_detail: List[int],
    embedder=None,
    mode: Optional[str] = None,
) -> Tuple[List[str], List[int], List[List[int]]]:
    """
    De-duplicate aspects according to the merge mode (see merge_mode()).

    Returns:
        (merged_aspects, merged_aspect_to_detail, parent_mapping)
        - merged_aspects: aspect texts after the merge (keeps the first occurrence)
        - merged_aspect_to_detail: detail index for each merged aspect
        - parent_mapping: for each merged aspect, list of original aspect indices it represents
    """
    mode = mode or merge_mode()
    n = len(aspects)
    if n <= 1 or mode == "off":
        return aspects, aspect_to_detail, [[i] for i in range(n)]

    if mode == "exact":
        seen: Dict[Tuple[int, frozenset], int] = {}
        merged_aspects, merged_to_detail, parent_mapping = [], [], []
        for i, text in enumerate(aspects):
            key = (aspect_to_detail[i], _normalized(text))
            if key in seen:
                parent_mapping[seen[key]].append(i)
                logger.info("Merging identical aspects of one detail question: '%s' | '%s'", aspects[parent_mapping[seen[key]][0]][:80], text[:80])
                continue
            seen[key] = len(merged_aspects)
            merged_aspects.append(text)
            merged_to_detail.append(aspect_to_detail[i])
            parent_mapping.append([i])
        return merged_aspects, merged_to_detail, parent_mapping

    # mode == "embedding": the old rule, kept unchanged so that stored runs can be rebuilt exactly
    if embedder is None:
        embedder = get_embedder()
    embeddings = embedder.encode(aspects, normalize_embeddings=True)
    merged = [False] * n
    parent_mapping = []
    merged_aspects = []
    merged_aspect_to_detail = []

    for i in range(n):
        if merged[i]:
            continue
        group = [i]
        merged[i] = True
        for j in range(i + 1, n):
            if merged[j]:
                continue
            sim = float(embeddings[i] @ embeddings[j])
            if sim >= NEAR_DUP_ASPECT_SIM:
                group.append(j)
                merged[j] = True
                logger.info(
                    f"Merging near-duplicate aspects (sim={sim:.3f}): "
                    f"'{aspects[i][:80]}' | '{aspects[j][:80]}'"
                )
        parent_mapping.append(group)
        merged_aspects.append(aspects[i])
        merged_aspect_to_detail.append(aspect_to_detail[i])

    return merged_aspects, merged_aspect_to_detail, parent_mapping


def flatten_aspects(
    detail_questions: List[str],
    sub_question_id: str,
    main_topic: str,
    merge_mode: Optional[str] = None,
) -> tuple[List[str], List[int]]:
    """
    Flatten all detail questions into a single list of aspects, then de-duplicate them (merge_mode, default from ASPECT_MERGE).

    Returns:
        (aspects_list, aspect_to_detail_map)
        - aspects_list: flattened list of all aspects (after the merge)
        - aspect_to_detail_map: for each aspect index, the original detail index (0-based)
    """
    all_aspects = []
    aspect_to_detail = []

    for detail_idx, detail in enumerate(detail_questions):
        aspects = split_detail_aspects(detail, sub_question_id, main_topic)
        for _ in aspects:
            aspect_to_detail.append(detail_idx)
        all_aspects.extend(aspects)

    merged_aspects, merged_mapping, _ = _merge_near_duplicate_aspects(all_aspects, aspect_to_detail, mode=merge_mode)

    return merged_aspects, merged_mapping


# ----------------------------------------------------------------------------------------------------- the sub-question's own question
def topic_aspect_enabled() -> bool:
    """TOPIC_ASPECT (default FALSE since 2026-11-06): the sub-question itself is judged as one more aspect.

    The aspects come from the planner's detail questions, which are generic ("advantages and disadvantages", "benefits", "challenges"). The
    sub-question's own question ("What is a mixture of experts model?") was never judged, so a sub-question could be "sufficient" without
    being answered (Q2, 2026-11-05: 4 of 5 sufficient; "What is a MoE model?" had no definition aspect). Experiment on 10 stored sub-questions
    (tests/topic_aspect_experiment.py): no judge errors, 17 of 21 "yes" claims directly answered the topic (81%, the rest partial), and two
    sub-questions changed from sufficient to not sufficient. The stored digests had been written without this aspect, so the experiment
    understates coverage.

    OFF BY DEFAULT because the aspect list is also what the digest prompt and the chunk selection receive: with the topic in it the digest
    model returned 1.50 findings per digest instead of 4.25 (-65%, same 6 sources, same chunks, each condition run twice; repeat spread 0.5;
    tests/topic_aspect_digest_experiment.py), and the first run through the API had 0 of 5 sub-questions sufficient against 4 of 5. The idea
    (judge the topic) is kept; the way it is wired is not: it should reach the judge and the coverage rule only, not the digest prompt."""
    return os.getenv("TOPIC_ASPECT", "false").strip().lower() in ("1", "true", "yes", "on")


def run_topic_aspect(coverage_row: Optional[Dict]) -> bool:
    """Whether a stored run judged the topic as an aspect (marker written into judge_stats); runs from before the marker did not."""
    return bool(((coverage_row or {}).get("judge_stats") or {}).get("topic_aspect"))


def with_topic_aspect(aspects: List[str], aspect_to_detail: List[int], detail_questions: List[str], main_topic: str,
                      enabled: Optional[bool] = None) -> tuple[List[str], List[int], List[str]]:
    """The aspects with the sub-question's own question appended as the LAST aspect (indexes of the other aspects stay the same), its
    own pseudo detail question appended to the details. Unchanged when disabled, when the topic is empty, or when an aspect already asks it."""
    enabled = topic_aspect_enabled() if enabled is None else enabled
    topic = " ".join((main_topic or "").split())
    if not enabled or not topic or any(_normalized(topic) == _normalized(a) for a in aspects):
        return list(aspects), list(aspect_to_detail), list(detail_questions)
    return list(aspects) + [topic], list(aspect_to_detail) + [len(detail_questions)], list(detail_questions) + [topic]
