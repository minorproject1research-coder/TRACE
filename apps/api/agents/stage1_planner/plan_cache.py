# apps/api/agents/stage1_planner/plan_cache.py
"""Opt-in cache of the planner's plan, so that a rerun of the same question plans the same way.

The planner is a LoRA adapter served by vLLM. It is not reproducible: three calls at temperature 0 gave three different plans, and a
fixed seed did not help (the base judge model on the same server IS reproducible, so the cause is the adapter path, not the wrapper;
see docs/reports/13_planner_determinism.md). Runs of the same question therefore started with different sub-questions, which made
run-to-run comparisons of Stage 2 and Stage 3 meaningless.

PLAN_CACHE=true stores the plan that /decompose returned (after parsing, before any merge or query anchoring) under the question and
reuses it on the next run. Default off: a normal run plans freshly. A plan that came from the Groq fallback is never cached, because it
is a degraded plan that would otherwise outlive the outage.

  PLAN_CACHE=true|false      switch (default false)
  PLAN_CACHE_DIR=...         directory (default .cache/plans)
  PLAN_CACHE_TAG=...         change it to start over after the planner or its prompt changed (part of the key)
Delete the file of a question (or the directory) to plan it again.
"""
import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger("apps.api.agents.stage1_planner")


def enabled() -> bool:
    return os.getenv("PLAN_CACHE", "true").strip().lower() in ("1", "true", "yes", "on")


def _cache_dir() -> Path:
    return Path(os.getenv("PLAN_CACHE_DIR", ".cache/plans"))


def cache_path(question: str) -> Path:
    normalized = " ".join(question.split())
    tag = os.getenv("PLAN_CACHE_TAG", "").strip()
    key = hashlib.sha256(f"{tag}|{normalized}".encode()).hexdigest()
    return _cache_dir() / f"{key}.json"


def _usable(plan) -> bool:
    return (isinstance(plan, dict) and isinstance(plan.get("sub_questions"), list) and bool(plan["sub_questions"])
            and isinstance(plan.get("search_queries"), list))


def load(question: str) -> dict | None:
    """The cached plan, or None (switch off, nothing stored, or the file is unreadable)."""
    if not enabled():
        return None
    try:
        data = json.loads(cache_path(question).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError, OSError):
        return None
    plan = data.get("plan") if isinstance(data, dict) else None
    if not _usable(plan):
        logger.warning("Plan cache file for this question is not usable; planning again")
        return None
    logger.info("Plan cache hit: reusing the stored plan (%d sub-questions, %d search queries)",
                len(plan["sub_questions"]), len(plan["search_queries"]))
    return plan


def store(question: str, plan: dict) -> None:
    if not enabled() or not _usable(plan):
        return
    path = cache_path(question)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"question": question.strip(), "plan": plan}, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
        logger.info("Plan cache: stored the plan (%s)", path.name)
    except OSError as e:
        logger.warning("plan cache write failed: %s", e)
