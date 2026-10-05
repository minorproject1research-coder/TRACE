"""Shared helpers: judge prompt, tolerant verdict parsing, jsonl IO."""
import json
import re

# Must stay identical to RELEVANCE_JUDGE_PROMPT in relevance_filter.py so the
# benchmark measures exactly what runs in production.
from apps.api.agents.stage2_retrieval.relevance_filter import (
    JUDGE_ABSTRACT_CHAR_LIMIT as ABSTRACT_CHAR_LIMIT,  # same truncation as llm_judge_relevance()
    RELEVANCE_JUDGE_PROMPT,
)


def build_judge_prompt(row: dict) -> str:
    return RELEVANCE_JUDGE_PROMPT.format(
        sub_question=row["sub_question"],
        title=row.get("title", ""),
        abstract=(row.get("abstract") or "")[:ABSTRACT_CHAR_LIMIT],
    )


def parse_verdict(raw: str) -> dict | None:
    """Extract the verdict JSON from a model reply. Returns None if unusable.
    Tolerates <think> blocks, code fences and surrounding prose."""
    if not raw:
        return None
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    candidates = [text]
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if m:
        candidates.append(m.group(0))
    for c in candidates:
        c = c.strip().strip("`")
        if c.startswith("json"):
            c = c[4:]
        try:
            obj = json.loads(c)
        except Exception:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("relevant"), bool):
            try:
                conf = float(obj.get("confidence", 0.0))
            except (TypeError, ValueError):
                conf = 0.0
            return {"relevant": obj["relevant"], "confidence": min(max(conf, 0.0), 1.0),
                    "reason": str(obj.get("reason", ""))}
    return None


def read_jsonl(path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
