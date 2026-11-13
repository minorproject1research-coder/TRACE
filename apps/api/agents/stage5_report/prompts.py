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
7. If a claim gives a percentage or a change (improved by, gain, drop, higher, lower), say what it is compared with, in the claim's own words (for example "compared with a model trained on public data"). If the claim does not say what it is compared with, do not state the percentage as a comparison.

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

ANSWER_SYSTEM = """You answer a research question for a reader, using ONLY numbered sentences that were already verified against sources. You write the {kind}: {low} to {high} sentences.

The question: {question}
{parts}
Rules:
1. Answer the question itself. The first sentence must give the verdict on the main part of the question in plain words (for example how the two things compare). Then give the numbers, conditions or limits that qualify it, then answer every other part of the question (for example the trade-offs). If the numbered sentences do not answer a part, say nothing about it: the system adds a note about what the evidence does not settle.
2. Use only what the numbered sentences say. Do not add any number, name, model, dataset or detail that is not in them. Do not change a number. Prefer sentences that contain a figure, and keep the figure with what it is compared with.
3. Each answer sentence is based on one to four numbered sentences: list their numbers in from_sentences. The sentences are grouped under "== Part: ... ==" headers. Write at least one answer sentence for each of three or more different parts, so that the answer covers the verdict, the conditions or limits, and the risks or costs when the parts have them.
4. Never sound more certain than the numbered sentences. A sentence based on ANY numbered sentence that starts "One source reports" or "One study reports" must itself start with "One study reports", "One source reports" or "According to one source,". Only a sentence based on sentences that ALL start "Two sources report" may start that way. Base each sentence on sentences of the same kind. Never turn a reported finding into a fact.
5. Do not write citations, reference numbers like [1], URLs, author names or years. The system adds the citations.
6. {extra}
7. At most 70 words per sentence.

Return only JSON: {{"sentences": [{{"text": "...", "from_sentences": [1, 2]}}]}}"""

ANSWER_PARTS_SYSTEM = """You answer a research question for a reader, using ONLY numbered sentences that were already verified against sources. The sentences are grouped under "== Part: ... ==" headers, one group for each part of the answer. You write the {kind}: exactly {n} sentences, ONE for each part, in the order of the parts.

The question: {question}

Rules:
1. Each answer sentence says, in plain words, what the numbered sentences of its own part say about the question. Base it on one or two numbered sentences of that part ONLY: list their numbers in from_sentences. Never mix sentences of different parts in one answer sentence.
2. Use only what the numbered sentences say. Do not add any number, name, model, dataset or detail that is not in them. Do not change a number. Keep a figure together with what it is compared with.
3. Never sound more certain than the numbered sentences. A sentence based on a numbered sentence that starts "One source reports" or "One study reports" must itself start with "One study reports", "One source reports" or "According to one source,". Only a sentence based on sentences that start "Two sources report" may start that way. Never turn a reported finding into a fact. If the two numbered sentences of a part point in different directions, give both sides ("One source reports X, while another reports Y").
4. Do not write citations, reference numbers like [1], URLs, author names or years. The system adds the citations.
5. {extra}
6. At most 60 words per sentence.

Return only JSON: {{"sentences": [{{"text": "...", "from_sentences": [1, 2]}}]}}"""

SUMMARY_EXTRA = {
    "summary": "Do not use connecting words such as therefore, thus, hence, consequently. Put the best supported points first.",
    "conclusion": "Give the bottom line: what a reader should take away, in plain words, and the main caveat, in three or four sentences. Do not repeat the summary. Leave out dataset and benchmark names and other detail that does not answer the question. Do not introduce a topic that is not in the numbered sentences. Do not recommend anything. Do not claim more than they say.",
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
def _numbered(sentences, parts=None) -> str:
    """sentences: list of {"n": int, "text": str, "tier": str}. With `parts` (the section titles by index) and a "section" on the sentences, a header line
    "== Part: <title> ==" starts each group, so the answer can be built part by part."""
    lines, last = [], object()
    for s in sentences:
        sec = s.get("section")
        if parts and isinstance(sec, int) and sec != last and 0 <= sec < len(parts):
            lines.append(f"== Part: {_cut(parts[sec], 160)} ==")
        last = sec
        lines.append(f'{s["n"]}. [{s.get("tier", "")}] {_cut(s["text"], 400)}')
    return "\n".join(lines)


def summary_messages(kind: str, sentences: list, low: int, high: int, context=None) -> list:
    """kind: "summary" or "conclusion". `sentences`: validated body sentences as {"n","text","tier"} (n = the number the model must cite).
    `context` = {"question": str, "parts": [str]} makes it an ANSWER to the question (the summary of template s5-v2); without it the old compress-only prompt."""
    extra = SUMMARY_EXTRA.get(kind, SUMMARY_EXTRA["summary"])
    question = str((context or {}).get("question") or "").strip()
    if question:
        parts = [str(x).strip() for x in ((context or {}).get("parts") or []) if str(x).strip()]
        nl = chr(10)
        parts_text = ("The report looked at these sub-questions; the sentences come from them:" + nl + nl.join(f"- {x}" for x in parts) + nl) if parts else ""
        if (context or {}).get("mode") == "parts":
            system = ANSWER_PARTS_SYSTEM.format(kind=kind, n=high, question=question, extra=extra)
        else:
            system = ANSWER_SYSTEM.format(kind=kind, low=low, high=high, question=question, parts=parts_text, extra=extra)
    else:
        system = SUMMARY_SYSTEM.format(kind=kind, low=low, high=high, extra=extra)
    parts_titles = (context or {}).get("parts") if question else None
    return [{"role": "system", "content": system}, {"role": "user", "content": f"Numbered sentences:\n{_numbered(sentences, parts_titles)}"}]


def summary_retry_messages(kind: str, sentences: list, low: int, high: int, previous: list, reasons: list, context=None) -> list:
    msgs = summary_messages(kind, sentences, low, high, context)
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
