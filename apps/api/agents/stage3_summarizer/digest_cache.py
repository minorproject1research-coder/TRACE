# apps/api/agents/stage3_summarizer/digest_cache.py
"""Cache of the digest LLM's parsed JSON reply, so re-running Stage 3 on the same sources gives the same findings.

Without it every Stage 3 run asks the model again and gets different findings (so a sub-question's coverage changed from run to run on
identical sources). One small file per key under DIGEST_CACHE_DIR (default .cache/digests, git-ignored).

Key = (sub_question_id, source_id, hash of the aspect list, model id, hash of the prompt TEMPLATE, sampling settings, hash of the
rendered prompt). The last part (question + aspects + chunk text) means a changed chunk selection or parse never reuses an old answer.
The raw reply is cached, not the verified findings: quote verification and tag parsing are code and run again on every call.

Switch off with DIGEST_CACHE=false. Failed calls are never cached (only parsed replies, including a legitimate empty findings list).
"""
import hashlib
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("apps.api.agents.stage3_summarizer.digest_cache")


def enabled() -> bool:
    return os.getenv("DIGEST_CACHE", "true").strip().lower() not in ("0", "false", "no", "off")


def _dir() -> Path:
    return Path(os.getenv("DIGEST_CACHE_DIR", ".cache/digests"))


def _h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_key(scope: tuple, aspects: Optional[List[str]], model: str, template: str, sampling: str, rendered_prompt: str) -> str:
    parts = [str(scope[0]), str(scope[1]), _h("\n".join(aspects or [])), model, _h(template), sampling, _h(rendered_prompt)]
    return _h("|".join(parts))


def get(key: str) -> Optional[dict]:
    path = _dir() / f"{key}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        logger.warning("digest cache entry %s unreadable (%s); regenerating", key[:12], e)
        return None


def put(key: str, data: dict) -> None:
    try:
        d = _dir()
        d.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, d / f"{key}.json")          # atomic: parallel digest workers never see half a file
    except OSError as e:
        logger.warning("digest cache write failed: %s", e)
