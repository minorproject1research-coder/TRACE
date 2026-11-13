"""Prompt templates and strict JSON schemas of Stage 5. Pure functions, no I/O: the same input always renders the same text, which is what the
cache key (writer.py) relies on. Raise `settings.TEMPLATE_VERSION` when a template changes.

Four prompts:
  write_messages    one section call: the jobs (1-3 claims each, with verbatim quotes) -> one sentence per job + the claim ids it used
  retry_messages    the same for the jobs that failed a Python check, with the previous sentence and the reasons Python wrote
  summary_messages  numbered, already validated sentences -> 3-5 summary sentences, each saying which numbered sentences it is based on
  conclusion_messages  the same compress-only task with a conclusion wording

The LLM never writes citations: the prompts forbid [n], URLs, author names and years, and Python adds the markers from the claim ids.
The tier wording comes from `hedging.TIER_RULES` (agent CHECK); `DEFAULT_TIER_TEXT` is only used for a tier that table does not cover.
"""
import json
import math

from apps.api.agents.stage5_report import schema

MAX_QUOTE_CHARS = 280           # a quote longer than this is cut in the prompt (the full quote stays in the database)
MAX_QUOTES_PER_CLAIM = 2
CHARS_PER_TOKEN = 4             # rough estimate, same rule as the budget notes

DEFAULT_TIER_TEXT = {
    schema.TIER_SUPPORTED: 'Two or more sources report this. Start with "Two sources report that" and state it plainly.',
    schema.TIER_PARTLY: 'One source reports the claim and another source makes a related point (shown as "related wording"). Say so, for example '
                        '"One source reports X; another makes a related point." Do not merge the two into one claim.',
    schema.TIER_SINGLE: 'Only one source reports this. Attribute it and never state it as fact: start with "One study reports that" or '
                        '"According to one source,". Do not use the verbs shows, proves, demonstrates, confirms, establishes.',
}

WRITE_SYSTEM = """You write sentences for a literature report. You get a list of JOBS. Each job has 1 to 3 CLAIMS taken from research sources, with their verbatim quotes.

Rules:
1. Write exactly ONE sentence per job, at most 60 words, saying what the claims of that job say and nothing else.
2. Use only the claims and quotes of that job. Do not add any number, name, model, dataset, method or detail that is not in them. Do not change a number.
3. Do not write citations, reference numbers like [1], URLs, author names or years. The system adds the citations.
4. Do not use connecting or concluding words such as therefore, thus, hence, overall, consequently, as a result, which suggests, this implies. Do not join claims into a bigger claim. Do not explain, compare or evaluate.
5. Keep the wording of the job's tier (see "Wording by tier").
6. In claim_ids list every claim id the sentence uses. Use only claim ids of that job.

Return only JSON: {"sentences": [{"job_id": "...", "text": "...", "claim_ids": ["..."]}]} with exactly one entry per job."""

SUMMARY_SYSTEM = """You compress numbered, already verified sentences from a literature report. You write the {kind}: {low} to {high} sentences.

Rules:
1. Use only what the numbered sentences say. Do not add any number, name, model, dataset or detail that is not in them. Do not change a number.
2. Each {kind} sentence is based on one to three numbered sentences: list their numbers in from_sentences.
3. Never sound more certain than the numbered sentences it is based on. If one of them says "one study reports" or "according to", keep that attribution. Never turn a reported finding into a fact.
   Concretely: a summary sentence that is based on ANY numbered sentence starting "One source reports" or "One study reports" must itself start with "One study reports" or "One source reports" (or "According to one source,"). Only a sentence based on sentences that ALL start with "Two sources report" may start that way. To avoid mixing, base each sentence on sentences of the same kind.
4. Do not write citations, reference numbers like [1], URLs, author names or years. The system adds the citations.
5. {extra}
6. At most 60 words per sentence.

Return only JSON: {{"sentences": [{{"text": "...", "from_sentences": [1, 2]}}]}}"""

SUMMARY_EXTRA = {
    "summary": "Do not use connecting words such as therefore, thus, hence, consequently. Put the best supported points first.",
    "conclusion": "Restate the main points only. Do not introduce a topic that is not in the numbered sentences. Do not recommend anything. Do not claim more than they say.",
}


# ------------------------------------------------------------------------------------------------------------ helpers
def estimate_tokens(text: str) -> int:
    return int(math.ceil(len(text or "") / CHARS_PER_TOKEN))


def estimate_messages_tokens(messages: list) -> int:
    return sum(estimate_tokens(m.get("content", "")) + 4 for m in messages)


def _cut(text: str, limit: int = MAX_QUOTE_CHARS) -> str:
    t = " ".join(str(text or "").split())
    return t if len(t) <= limit else t[:limit - 3].rstrip() + "..."


def tier_instruction(tier: str, tier_rules=None) -> str:
    """The instruction text of a tier. `tier_rules` is `hedging.TIER_RULES`: per tier a string, or a dict with the instruction under one of the
    keys instruction / prompt / text / rule. Anything else (or a tier missing there) uses DEFAULT_TIER_TEXT."""
    rule = (tier_rules or {}).get(tier) if hasattr(tier_rules or {}, "get") else None
    if isinstance(rule, str) and rule.strip():
        return rule.strip()
    if isinstance(rule, dict):
        for key in ("instruction", "prompt", "text", "rule"):
            if isinstance(rule.get(key), str) and rule[key].strip():
                return rule[key].strip()
    return DEFAULT_TIER_TEXT.get(tier, "")


def render_job(job) -> str:
    """One job as text: id, tier and its claims with their quotes (supporting quotes; for a "partly" claim also the related wording)."""
    lines = [f"JOB {job.job_id} (tier: {job.tier})"]
    for c in job.claims:
        lines.append(f"  claim {c.claim_id}: {_cut(c.text, 400)}")
        supporting = [e for e in getattr(c, "evidence", []) if getattr(e, "relation", "supports") == "supports"]
        for e in supporting[:MAX_QUOTES_PER_CLAIM]:
            lines.append(f'    quote: "{_cut(e.quote)}"')
        if job.tier == schema.TIER_PARTLY:
            for e in [e for e in getattr(c, "evidence", []) if getattr(e, "relation", "") == "near_match"][:1]:
                if getattr(e, "near_claim", None):
                    lines.append(f'    related wording from another source: "{_cut(e.near_claim)}"')
                if getattr(e, "quote", None):
                    lines.append(f'    its quote: "{_cut(e.quote)}"')
    return "\n".join(lines)


def _tier_block(jobs, tier_rules) -> str:
    seen = []
    for j in jobs:
        if j.tier not in seen:
            seen.append(j.tier)
    return "\n".join(f"- {t}: {tier_instruction(t, tier_rules)}" for t in seen)


def _write_user(section_title: str, jobs, tier_rules) -> str:
    return (f'Section: "{_cut(section_title, 300)}"\n\nWording by tier:\n{_tier_block(jobs, tier_rules)}\n\n'
            "JOBS\n" + "\n\n".join(render_job(j) for j in jobs))


# ------------------------------------------------------------------------------------------------------------ section prompts
def write_messages(section_title: str, jobs, tier_rules=None) -> list:
    return [{"role": "system", "content": WRITE_SYSTEM}, {"role": "user", "content": _write_user(section_title, jobs, tier_rules)}]


def retry_messages(section_title: str, jobs, previous: dict, tier_rules=None) -> list:
    """The retry: the failed jobs again, and for each the previous sentence and the reasons Python found. `previous` = {job_id: {"text": str,
    "reasons": [str]}}. The reasons are specific ("the number 17% is not in the claims"), because the model cannot find its own mistake."""
    parts = []
    for j in jobs:
        p = previous.get(j.job_id) or {}
        reasons = "\n".join(f"    - {r}" for r in p.get("reasons", [])) or "    - no usable sentence was returned"
        prev = _cut(p.get("text", ""), 500) or "(none)"
        parts.append(f'JOB {j.job_id}\n  previous sentence: "{prev}"\n  it was rejected because:\n{reasons}')
    note = ("Your earlier answer for the jobs below was rejected by automatic checks. Write each sentence again and fix exactly the problems "
            "listed. Follow all the rules. Return one entry per job.\n\n" + "\n\n".join(parts))
    return [{"role": "system", "content": WRITE_SYSTEM},
            {"role": "user", "content": _write_user(section_title, jobs, tier_rules) + "\n\n" + note}]


def section_schema(jobs) -> dict:
    """Strict json_schema for response_format. job_id and claim_ids are enums of the ids of THIS call, so the model cannot invent an id."""
    claim_ids = []
    for j in jobs:
        for c in j.claims:
            if c.claim_id not in claim_ids:
                claim_ids.append(c.claim_id)
    return {"type": "json_schema", "json_schema": {"name": "stage5_sentences", "strict": True, "schema": {
        "type": "object", "additionalProperties": False, "required": ["sentences"],
        "properties": {"sentences": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["job_id", "text", "claim_ids"],
            "properties": {"job_id": {"type": "string", "enum": [j.job_id for j in jobs]},
                           "text": {"type": "string"},
                           "claim_ids": {"type": "array", "items": {"type": "string", "enum": claim_ids}}}}}}}}}


# ------------------------------------------------------------------------------------------------------------ summary / conclusion
def _numbered(sentences) -> str:
    """sentences: list of {"n": int, "text": str, "tier": str}."""
    return "\n".join(f'{s["n"]}. [{s.get("tier", "")}] {_cut(s["text"], 400)}' for s in sentences)


def summary_messages(kind: str, sentences: list, low: int, high: int) -> list:
    """kind: "summary" or "conclusion". `sentences`: validated body sentences as {"n","text","tier"} (n = the number the model must cite)."""
    system = SUMMARY_SYSTEM.format(kind=kind, low=low, high=high, extra=SUMMARY_EXTRA.get(kind, SUMMARY_EXTRA["summary"]))
    return [{"role": "system", "content": system}, {"role": "user", "content": f"Numbered sentences:\n{_numbered(sentences)}"}]


def summary_retry_messages(kind: str, sentences: list, low: int, high: int, previous: list, reasons: list) -> list:
    msgs = summary_messages(kind, sentences, low, high)
    prev = "\n".join(f'- "{_cut(p, 300)}"' for p in previous) or "(none)"
    why = "\n".join(f"- {r}" for r in reasons) or "- no usable answer was returned"
    msgs[1]["content"] += (f"\n\nYour earlier answer was rejected by automatic checks.\nEarlier answer:\n{prev}\nRejected because:\n{why}\n"
                           f"Write the {kind} again and fix exactly these problems.")
    return msgs


def summary_schema(numbers: list) -> dict:
    return {"type": "json_schema", "json_schema": {"name": "stage5_summary", "strict": True, "schema": {
        "type": "object", "additionalProperties": False, "required": ["sentences"],
        "properties": {"sentences": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["text", "from_sentences"],
            "properties": {"text": {"type": "string"},
                           "from_sentences": {"type": "array", "items": {"type": "integer", "enum": list(numbers)}}}}}}}}}


def dumps(messages: list) -> str:
    """The rendered prompt as one stable string (cache key input)."""
    return json.dumps(messages, ensure_ascii=False, sort_keys=True)
