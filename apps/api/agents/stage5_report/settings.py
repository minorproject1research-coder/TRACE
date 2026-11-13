"""Switches and numbers of Stage 5 (the written report). Every value is read from the environment at CALL time (like `factcheck_enabled()` in
apps/api/config.py), so a test or a restart-free change takes effect at once. A bad value (not a number, empty) falls back to the default.

    STAGE5=false                        whole stage off (1/true/yes/on switches it on)
    STAGE5_MODEL=openai/gpt-oss-120b    the writer model (through groq_pool)
    STAGE5_REASONING_EFFORT=low         low | medium | high (gpt-oss cannot switch reasoning off)
    STAGE5_MAX_OUTPUT_TOKENS=2500       max_completion_tokens of one call
    STAGE5_MAX_PROMPT_TOKENS=4500       a section whose jobs do not fit is split into several calls (about 4 characters per token)
    STAGE5_TEMPERATURE=0.2
    STAGE5_RETRIES=1                    retries of a failed sentence, with the Python-written reasons, before the deterministic sentence
    STAGE5_WORKERS=3                    calls (sections) at the same time
    STAGE5_CACHE=true                   validated replies are cached on disk
    STAGE5_CACHE_DIR=.cache/stage5
    STAGE5_RATE_WAIT_MAX=300            a pool-wide rate limit of at most this many seconds is waited out; the same meaning as STAGE4_RATE_WAIT_MAX
    STAGE5_RATE_RETRIES=2               how many times a call waits and asks again
    STAGE5_BREAKER_SECONDS=300          after a limit that cannot be waited out the model is not asked again for this long
"""
import os

TEMPLATE_VERSION = "s5-v2"      # part of every cache key: raise it when a prompt changes
DEFAULT_MODEL = "openai/gpt-oss-120b"
_TRUE = ("1", "true", "yes", "on")
_FALSE = ("0", "false", "no", "off")


def _int(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default)).strip()))
    except (ValueError, AttributeError):
        return default


def _float(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(os.getenv(name, str(default)).strip()))
    except (ValueError, AttributeError):
        return default


def stage5_enabled() -> bool:
    """STAGE5 (default true since 2026-11-13; STAGE5=false switches it off) runs Stage 5 after Stage 4."""
    return os.getenv("STAGE5", "true").strip().lower() in _TRUE


def embed_select() -> bool:
    """STAGE5_EMBED_SELECT (default true): the sentence of each part of the answer is chosen by embedding similarity to the question and to the section (the bge
    model of Stage 2); false or an error: by word overlap."""
    return os.getenv("STAGE5_EMBED_SELECT", "true").strip().lower() in _TRUE


def model() -> str:
    return os.getenv("STAGE5_MODEL", "").strip() or DEFAULT_MODEL


def reasoning_effort() -> str:
    v = os.getenv("STAGE5_REASONING_EFFORT", "low").strip().lower()
    return v if v in ("low", "medium", "high") else "low"


def max_output_tokens() -> int:
    return _int("STAGE5_MAX_OUTPUT_TOKENS", 2500, minimum=100)


def max_prompt_tokens() -> int:
    return _int("STAGE5_MAX_PROMPT_TOKENS", 4500, minimum=200)


def temperature() -> float:
    return _float("STAGE5_TEMPERATURE", 0.2)


def retries() -> int:
    return _int("STAGE5_RETRIES", 1)


def workers() -> int:
    return _int("STAGE5_WORKERS", 3, minimum=1)


def cache_enabled() -> bool:
    return os.getenv("STAGE5_CACHE", "true").strip().lower() not in _FALSE


def cache_dir() -> str:
    return os.getenv("STAGE5_CACHE_DIR", "").strip() or ".cache/stage5"


def rate_wait_max() -> float:
    return _float("STAGE5_RATE_WAIT_MAX", 300.0)


def rate_retries() -> int:
    return _int("STAGE5_RATE_RETRIES", 2)


def breaker_seconds() -> float:
    return _float("STAGE5_BREAKER_SECONDS", 300.0)


def style() -> str:
    """STAGE5_STYLE: "natural" (template s5-v3; NOT the default yet: it has unit tests but no clean live run, the Groq limit was exhausted on 2026-11-13) writes plain claims, the strength of the evidence is shown by the tier label and the citations,
    a single-source claim names what its source is ("A PET/CT study reports ..."); "attributed" is the s5-v2 wording ("One source reports that ...",
    "Two sources report that ...") in every sentence."""
    return "natural" if os.getenv("STAGE5_STYLE", "attributed").strip().lower() == "natural" else "attributed"


def natural() -> bool:
    return style() == "natural"


def template_version() -> str:
    return "s5-v3" if natural() else TEMPLATE_VERSION
