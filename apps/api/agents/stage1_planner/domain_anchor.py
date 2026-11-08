# apps/api/agents/stage1_planner/domain_anchor.py
"""Domain anchor: keep the field of the ORIGINAL question in the later stages.

The fine-tuned planner writes generic background sub-questions and queries ("What are transformers and how do they work?",
"state space models overview") without the field of the original question. Search engines then return electrical-power
transformers and statistical / econometric state-space models, and the relevance judge, which only sees the sub-question, has
no way to know they are the wrong field. The planner is not changed (it is fine-tuned); instead one cheap LLM call derives
two short pieces of text from the original question, once per question:

  anchor   1-4 words naming the field ("deep learning"), appended to every search query and to the text the embedding
           pre-filter compares with the abstracts;
  context  one sentence naming the field and the intended meaning of the ambiguous terms (and what is NOT meant), appended to the
           sub-question text the relevance judge sees.

Both are empty when the question is already unambiguous, and also when the call fails (the pipeline then behaves as before).
The result is cached per question so a rerun searches the same way. Switch: DOMAIN_ANCHOR=true|false (default true).

Why an LLM call and not a rule: the original question has the field only implicitly (nothing in 'How do state space models like
Mamba compare with transformers' says 'deep learning'). Appending a distinctive word from the question instead (e.g. 'Mamba') steers
too hard: the background question 'What are transformers?' then returns only Mamba papers. The anchor must be a neutral field phrase,
narrow enough to exclude the other meaning: 'machine learning' still returned power-transformer fault-prediction papers, 'deep learning'
did not. The prompt therefore reasons first (which terms are ambiguous) and shows worked examples from unrelated questions.
"""
import hashlib
import json
import logging
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("apps.api.agents.stage1_planner")

MAX_ANCHOR_WORDS = 4
MAX_ANCHOR_CHARS = 40
MAX_CONTEXT_CHARS = 300

PROMPT = """You help a research assistant search the right field. A word in a research question can also be a technical term in another field, and a search engine then returns papers from the wrong field.

Return ONLY a JSON object in exactly this format:
{{"ambiguous": "...", "anchor": "...", "context": "..."}}

- "ambiguous": one sentence naming the terms of the question that are ambiguous across fields, the meaning intended here and the other meaning; "none" if no term is.
- "anchor": 1 to 3 words that name the intended field so that papers with the other meaning stop matching. Name the field narrowly enough to exclude the other meaning, and do not repeat words from the question. "" when "ambiguous" is "none".
- "context": ONE sentence stating the intended field and meaning of the ambiguous terms and what is not meant. "" when the anchor is "".

Examples:
Question: How do recurrent neural networks compare with transformers on machine translation?
{{"ambiguous": "'transformers' is the neural network architecture here, but also means electrical transformers.", "anchor": "deep learning", "context": "Deep learning: Transformers are the neural network architecture, not electrical transformers."}}
Question: What causes transformer overheating in electrical substations?
{{"ambiguous": "'transformer' means the electrical device here, not the neural network architecture.", "anchor": "power systems", "context": "Power engineering: transformers are electrical devices, not neural network architectures."}}
Question: Which optimizers are used to train convolutional neural networks?
{{"ambiguous": "none", "anchor": "", "context": ""}}
Question: How does cell size affect the capacity of lithium-ion batteries?
{{"ambiguous": "'cell' means a battery cell here, not a biological cell.", "anchor": "battery electrochemistry", "context": "Battery engineering: cells are electrochemical cells, not biological cells."}}
Question: How effective is metformin for type 2 diabetes?
{{"ambiguous": "none", "anchor": "", "context": ""}}

Question: {question}"""


@dataclass(frozen=True)
class DomainAnchor:
    anchor: str = ""
    context: str = ""

    def __bool__(self) -> bool:
        return bool(self.anchor or self.context)


def enabled() -> bool:
    return os.getenv("DOMAIN_ANCHOR", "true").strip().lower() not in ("0", "false", "no", "off")


def _cache_dir() -> Path:
    return Path(os.getenv("DOMAIN_ANCHOR_CACHE_DIR", ".cache/domain_anchor"))


def _cache_key(question: str, model: str) -> str:
    return hashlib.sha256(f"{model}|{hashlib.sha256(PROMPT.encode()).hexdigest()}|{question.strip()}".encode()).hexdigest()


_PUNCTUATION = {ord(c): "-" for c in "‐‑‒–—―−"}
_PUNCTUATION.update({ord(c): "'" for c in "‘’‛"})
_PUNCTUATION.update({ord(c): '"' for c in "“”"})


def _clean(value, max_chars: int) -> str:
    if not isinstance(value, str):
        return ""
    # typographic hyphens and quotes become plain ASCII: a non-breaking hyphen made the Windows log file (cp1252) drop the whole line
    value = value.translate(_PUNCTUATION)
    value = re.sub(r"\s+", " ", value).strip().strip('"').strip()
    return value if len(value) <= max_chars else ""


def _validate(data) -> DomainAnchor:
    """Take what the model returned; anything unusable becomes empty rather than an error."""
    if not isinstance(data, dict):
        return DomainAnchor()
    anchor = _clean(data.get("anchor"), MAX_ANCHOR_CHARS)
    if len(anchor.split()) > MAX_ANCHOR_WORDS or re.search(r"[\[\]{}<>]", anchor):
        anchor = ""
    context = _clean(data.get("context"), MAX_CONTEXT_CHARS) if anchor else ""
    return DomainAnchor(anchor, context)


def generate(raw_query: str) -> DomainAnchor:
    """The anchor and context for a question; empty when the switch is off, the model sees no ambiguity, or the call fails."""
    if not enabled() or not raw_query.strip():
        return DomainAnchor()
    from apps.api.services import llm_service           # imported here so tests of the helpers need no LLM client

    key = _cache_key(raw_query, llm_service.MODEL_NAME)
    path = _cache_dir() / f"{key}.json"
    try:
        cached = json.loads(path.read_text(encoding="utf-8"))
        result = DomainAnchor(cached.get("anchor", ""), cached.get("context", ""))
        logger.info("Domain anchor (cached): %r | context: %s", result.anchor, result.context or "-")
        return result
    except (FileNotFoundError, ValueError, OSError):
        pass

    try:
        result = _validate(llm_service.squeezer_json(PROMPT.format(question=raw_query.strip()), temperature=0.0, purpose="domain_anchor"))
    except Exception as e:                               # never let this break planning; the pipeline then runs as before
        logger.warning("Domain anchor unavailable (%s: %s); searching without it", type(e).__name__, e)
        return DomainAnchor()
    try:
        _cache_dir().mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=_cache_dir(), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"anchor": result.anchor, "context": result.context, "question": raw_query.strip()}, f, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError as e:
        logger.warning("domain anchor cache write failed: %s", e)
    logger.info("Domain anchor: %r | context: %s", result.anchor, result.context or "-")
    return result


# ---------------------------------------------------------------- applying it (pure functions)

def _words(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def apply_to_queries(queries: list, anchor: str) -> list:
    """Append the anchor to each search query unless the query already contains all its words; exact duplicates are dropped."""
    if not anchor:
        return list(queries)
    anchor_words = _words(anchor)
    out = []
    for q in queries:
        q2 = q if anchor_words <= _words(q) else f"{q} {anchor}"
        if q2 not in out:
            out.append(q2)
    return out


def similarity_text(sub_question: str, anchor: str) -> str:
    """The text the embedding pre-filter compares with the abstracts."""
    return f"{sub_question} ({anchor})" if anchor else sub_question


def judge_text(sub_question: str, context: str) -> str:
    """The question text the relevance judge sees."""
    return f"{sub_question} [Field: {context}]" if context else sub_question
