"""Hedging rules of Stage 5: the WORDING that each tier allows. Python owns the hedge, never the LLM (an LLM does not hedge in step with what it
knows; see the notes in docs/STAGE5.md). The tier is set by Stage 4's label and the number of documents; this module only says

  * what the prompt must tell the writer for each tier (`TIER_RULES[tier]["instruction"]` and the example openers),
  * how to check that a written sentence keeps the tier's wording (`check_hedge`),
  * how to word a job deterministically when the LLM sentence failed its checks twice (`fallback_sentence`).

Pure Python, no model, no network, no environment switches (the word lists are constants at the top; edit them here).
"""
import re
from typing import Optional

from apps.api.agents.stage5_report import settings

from apps.api.agents.stage5_report.schema import (
    ORIGIN_FALLBACK, TIER_DISPUTED, TIER_PARTLY, TIER_SINGLE, TIER_SUPPORTED, TIERS, Sentence,
)

# ------------------------------------------------------------------------------------------------------------------ word lists
_DOC_SINGULAR = r"(?:study|source|paper|document|article|report|preprint|publication|page|webpage|web page|web source|text)"
_DOC_PLURAL = r"(?:studies|sources|papers|documents|articles|reports|preprints|publications|pages|webpages|web pages|web sources|texts)"

# The sentence must START with one of these (single and partly tiers). Matched on the lowercased sentence with surrounding quotes removed.
SINGLE_OPENERS = [
    rf"^(?:one|a single|a lone|only one)\s+(?:\w+\s+)?{_DOC_SINGULAR}\b",
    rf"^according to\s+(?:one|a single|only one)\s+(?:\w+\s+)?{_DOC_SINGULAR}\b",
]
SUPPORTED_OPENERS = [rf"^(?:two|three|four|five|several|multiple)\s+(?:independent\s+)?{_DOC_PLURAL}\b"]   # recommended, not required

# partly tier: besides the opener the sentence must say that the second document makes a related (not identical) point.
PARTLY_MARKERS = [r"\b(?:related|similar|close(?:ly)?|comparable|overlapping|partly|partially|in part|variant|narrower|broader|slightly different)\b"]

# Verbs and adverbs that state a fact instead of attributing it. Forbidden for single and partly; the "strong" short list also for supported.
_ATTRIBUTION_FORBIDDEN = [
    "shows", "show", "showed", "shown", "proves", "prove", "proved", "proven", "demonstrates", "demonstrate", "demonstrated",
    "confirms", "confirm", "confirmed", "establishes", "establish", "established", "verifies", "verified", "validates", "validated",
    "evidences", "clearly", "definitely", "undoubtedly", "certainly", "obviously", "conclusively", "definitively", "undeniably",
    "widely", "universally", "consensus", "well-established", "well established", "well-known", "well known", "it is known", "is known",
]
_SUPPORTED_FORBIDDEN = [
    "proves", "prove", "proved", "proven", "establishes", "established", "conclusively", "definitively", "undeniably", "undoubtedly",
    "beyond doubt", "universally",
]
# several sources named in a sentence that has one source behind it
_MANY_SOURCES_RE = re.compile(
    rf"\b(?:two|three|four|five|six|several|multiple|many|numerous|both|various)\s+(?:independent\s+)?{_DOC_PLURAL}\b"
    rf"|\bother\s+{_DOC_PLURAL}\b|\bmost\s+{_DOC_PLURAL}\b|\ball\s+{_DOC_PLURAL}\b", re.I)

TIER_RULES = {
    TIER_SUPPORTED: {
        "label": "supported (two or more documents state it)",
        "instruction": ("Two or more documents state this. Write it as a plain report of what the sources say, for example "
                        "\"Two sources report that ...\" or \"Several sources report that ...\". Say \"report\" or \"find\"; do not write "
                        "\"proves\", \"establishes\", \"conclusively\" or similar. Do not add anything the claims do not say."),
        "examples": ["Two sources report that ...", "Several sources report that ..."],
        "opener_patterns": SUPPORTED_OPENERS,
        "opener_required": False,
        "required_any": [],
        "forbidden_verbs": _SUPPORTED_FORBIDDEN,
    },
    TIER_PARTLY: {
        "label": "partly supported (one document states it, another a close variant)",
        "instruction": ("One document states the first claim and another document makes a related but not identical point. Start the sentence with "
                        "\"One source reports ...\" (or \"One study reports ...\"), then say that another source makes a related point and "
                        "state that point in its own wording, for example \"One source reports that X, while another makes a related point "
                        "that Y.\" Never write that the two agree or that X is established. Do not use \"shows\", \"proves\", \"demonstrates\", "
                        "\"confirms\" or \"establishes\"."),
        "examples": ["One source reports that X, while another makes a related point that Y."],
        "opener_patterns": SINGLE_OPENERS,
        "opener_required": True,
        "required_any": PARTLY_MARKERS,
        "forbidden_verbs": _ATTRIBUTION_FORBIDDEN,
    },
    TIER_SINGLE: {
        "label": "single source (one document states it; not confirmed elsewhere)",
        "instruction": ("Only ONE document states this and nothing else in the evidence confirms it, so never present it as fact. Start the sentence "
                        "with \"One study reports that ...\", \"One source reports that ...\" or \"According to one source, ...\". Do not write "
                        "\"shows\", \"proves\", \"demonstrates\", \"confirms\", \"establishes\" or \"clearly\", and do not mention other "
                        "sources or say that several studies agree."),
        "examples": ["One study reports that ...", "One source reports that ...", "According to one source, ..."],
        "opener_patterns": SINGLE_OPENERS,
        "opener_required": True,
        "required_any": [],
        "forbidden_verbs": _ATTRIBUTION_FORBIDDEN,
    },
}

# ---- natural style (template s5-v3): plain claims; the tier label and the citations carry the strength of the evidence
_SOURCE_NOUN = r"(?:study|source|paper|report|review|survey|trial|experiment|experiments|analysis|evaluation|benchmark|article|preprint|work|investigation|simulation|framework|case study|meta-analysis)"
NATURAL_SINGLE_ATTRIBUTION = [
    rf"^(?:a|an|one|the)\s+(?:[\w\-/]+\s+){{0,5}}?{_SOURCE_NOUN}\b",
    rf"^in\s+(?:a|an|one|the)\s+(?:[\w\-/]+\s+){{0,6}}?{_SOURCE_NOUN}\b",
    r"^according to\b", r"^(?:reportedly|per)\b",
]
TIER_RULES_NATURAL = {
    TIER_SUPPORTED: {
        "label": "supported (two or more documents state it)",
        "instruction": ("Two or more documents state this. Write it as a plain statement of the finding in natural scientific prose (for example "
                        "\"Federated models reach accuracy comparable to centralized pooling.\"); do not begin with \"Two sources report\". Do not write "
                        "\"proves\", \"establishes\", \"conclusively\" or \"universally\". Do not add anything the claims do not say."),
        "examples": ["Federated models reach accuracy comparable to centralized pooling."],
        "opener_patterns": [], "opener_required": False, "required_any": [], "forbidden_verbs": _SUPPORTED_FORBIDDEN,
    },
    TIER_PARTLY: {
        "label": "partly supported (one document states it, another a close variant)",
        "instruction": ("One document states this and another document makes a close but not identical point. Write ONE plain sentence in natural scientific "
                        "prose that says what the claim says; if the two wordings differ in what they say, say how (\"...; a related result is ...\"). "
                        "Do not begin with \"One source reports\" and do not write \"another source\". Use a reporting or hedged verb (reports, finds, "
                        "suggests, appears to, is associated with) when it reads naturally. Never write \"shows\", \"proves\", \"demonstrates\", "
                        "\"confirms\", \"establishes\" or \"clearly\"."),
        "examples": ["Federated training matches centralized accuracy on multi-site data; a related result is that it degrades under strong site heterogeneity."],
        "opener_patterns": [], "opener_required": False, "required_any": [], "forbidden_verbs": _ATTRIBUTION_FORBIDDEN,
    },
    TIER_SINGLE: {
        "label": "single source (one document states it; not confirmed elsewhere)",
        "instruction": ("Only ONE document states this and nothing else confirms it, so never present it as fact. Start the sentence by saying what the source is, "
                        "in natural words taken from the claim or the quote: \"A PET/CT segmentation study reports that ...\", \"In a benchmark on chest X-rays, "
                        "...\", \"A systematic review finds that ...\", \"According to one study, ...\". Never write \"One source reports\" if a better description "
                        "of the source is in the claim or quote. Do not write \"shows\", \"proves\", \"demonstrates\", \"confirms\", \"establishes\" or \"clearly\", "
                        "and do not mention other sources or say that several studies agree."),
        "examples": ["A PET/CT segmentation study reports that ...", "In a benchmark on chest X-rays, ...", "According to one study, ..."],
        "opener_patterns": NATURAL_SINGLE_ATTRIBUTION, "opener_required": True, "required_any": [], "forbidden_verbs": _ATTRIBUTION_FORBIDDEN,
    },
}


def rules() -> dict:
    """The tier rules of the active style (STAGE5_STYLE)."""
    return TIER_RULES_NATURAL if settings.natural() else TIER_RULES


def has_natural_attribution(text: str) -> bool:
    t = _norm(text).lower()
    return any(re.search(p, t) for p in NATURAL_SINGLE_ATTRIBUTION)


def natural_summary_problem(weakest_tier: str, text: str) -> Optional[str]:
    """Natural style: the problem (or None) of a summary / answer sentence whose weakest source sentence is of `weakest_tier`: a single-source sentence must say what
    its source is, a partly supported one may not state the finding with a fact verb; a supported one is free (its forbidden words are checked elsewhere)."""
    t = _norm(text)
    if weakest_tier == TIER_SINGLE:
        if not has_natural_attribution(t):
            return "it rests on one source: start by saying what the source is (\"A ... study reports that ...\", \"According to one study, ...\")"
        m = _FORBIDDEN_RE[TIER_SINGLE].search(t)
        if m:
            return f"the word '{m.group(0).lower()}' states a single-source finding as fact"
    if weakest_tier == TIER_PARTLY:
        m = _FORBIDDEN_RE[TIER_PARTLY].search(t)
        if m:
            return f"the word '{m.group(0).lower()}' states a partly supported finding as fact"
    return None


# order of strength used by the summary check: a summary sentence may never be stronger than the weakest body sentence it summarises
STRENGTH = {TIER_SINGLE: 1, TIER_PARTLY: 2, TIER_SUPPORTED: 3}


# ------------------------------------------------------------------------------------------------------------------ helpers
def _norm(text: str) -> str:
    t = (text or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", t).strip().strip("\"'").strip()


def _word_re(words) -> re.Pattern:
    return re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(w) for w in sorted(set(words), key=len, reverse=True)) + r")(?![\w-])", re.I)


_FORBIDDEN_RE = {t: _word_re(r["forbidden_verbs"]) for t, r in TIER_RULES.items()}


def has_opener(tier: str, text: str) -> bool:
    t = _norm(text).lower()
    return any(re.search(p, t) for p in rules().get(tier, {}).get("opener_patterns", []))


def has_partly_marker(text: str) -> bool:
    t = _norm(text).lower()
    return any(re.search(p, t) for p in PARTLY_MARKERS)


def hedge_level(text: str) -> str:
    """The tier whose wording a sentence carries, read from its words: single (one-source opener), partly (opener plus a "related point" marker)
    or supported (everything else). Used by the summary check to compare a summary sentence with the body sentences it summarises."""
    t = _norm(text).lower()
    one_source = any(re.search(p, t) for p in SINGLE_OPENERS) or re.search(rf"\b(?:one|a single|only one)\s+(?:\w+\s+)?{_DOC_SINGULAR}\b", t) \
        or re.search(r"\breportedly\b", t)
    if one_source and has_partly_marker(t):
        return TIER_PARTLY
    if one_source:
        return TIER_SINGLE
    return TIER_SUPPORTED


def strength(tier: Optional[str], text: str = "") -> int:
    """Strength 1 (single) to 3 (supported) of a body sentence: its tier when it has one, otherwise read from the words."""
    return STRENGTH.get(tier or "", STRENGTH[hedge_level(text)])


def _head(text: str, n: int = 6) -> str:
    """The attribution part of a sentence: the words before the first "that", comma or colon (at most n words)."""
    t = re.split(r"\s+that\s+|[,:;]", _norm(text), maxsplit=1)[0]
    return " ".join(t.split()[:n])


def check_hedge(tier: str, text: str, claim_text: str = "") -> list[str]:
    """Reasons why `text` does not keep the wording of `tier` (empty list = fine).

    single / partly: the sentence must open with an attribution ("One study reports ...", "According to one source, ..."); partly must also say
    that another source makes a RELATED point; neither may use a verb or adverb that states a fact ("shows", "proves", "demonstrates",
    "confirms", "establishes", "clearly", "widely") or name several sources. supported: only the strongest overclaims are forbidden ("proves",
    "establishes", "conclusively"). A forbidden word that is part of the CLAIM's own wording (`claim_text`, optional) is tolerated unless it sits
    in the opening words, where the verb that reports the claim stands ("One study shows ..." stays wrong even if the claim says "shows")."""
    if tier == TIER_DISPUTED:
        return ["disputed claims are never written as prose (they belong in the 'Sources disagree' section)"]
    rules_ = globals()["rules"]().get(tier)
    if rules_ is None:
        return [f"unknown tier '{tier}'"]
    t = _norm(text)
    reasons: list[str] = []
    if rules_["opener_required"] and not has_opener(tier, t):
        reasons.append("must open with an attribution such as: " + " / ".join(f'"{e}"' for e in rules_["examples"]))
    if tier == TIER_PARTLY and not settings.natural() and not has_partly_marker(t):
        reasons.append("must say that another source makes a related point (use the word 'related')")
    head = _head(t).lower()
    claim_l = (claim_text or "").lower()
    for m in _FORBIDDEN_RE[tier].finditer(t):
        w = m.group(0).lower()
        in_head = bool(re.search(r"(?<![\w-])" + re.escape(w) + r"(?![\w-])", head))
        if in_head or w not in claim_l:
            reasons.append(f"the word '{w}' states the claim as fact; use an attribution such as 'reports'")
            break
    if tier in (TIER_SINGLE, TIER_PARTLY):
        m = _MANY_SOURCES_RE.search(t)
        if m:
            reasons.append(f"'{m.group(0)}': this tier rests on one source, do not mention several sources")
    return reasons


def strip_attribution(text: str) -> str:
    """The sentence without its leading attribution ("One study reports that X" -> "X"), so that the entailment check compares the CONTENT with the
    evidence (the quote does not say "one study reports"). Returns the text unchanged when no opener is found or little would be left."""
    t = _norm(text)
    verbs = (r"(?:report|reports|reported|state|states|stated|find|finds|found|note|notes|noted|describe|describes|described|observe|observes|observed|"
             r"claim|claims|claimed|say|says|said|present|presents|presented|mention|mentions|mentioned|measure|measures|measured|indicate|indicates|"
             r"indicated|suggest|suggests|suggested|document|documents|documented|conclude|concludes|concluded|argue|argues|argued|propose|proposes|"
             r"proposed|provide|provides|provided|give|gives|gave|offer|offers|offered)\b")
    pats = [
        rf"^according to\s+(?:one|a single|only one|two|several|multiple)\s+(?:\w+\s+)?(?:{_DOC_SINGULAR}|{_DOC_PLURAL})\s*,?\s*",
        rf"^(?:one|a single|a lone|only one|two|three|four|five|several|multiple)\s+(?:independent\s+)?(?:\w+\s+)?(?:{_DOC_SINGULAR}|{_DOC_PLURAL})"
        rf"\s+(?:also\s+)?{verbs}\s*(?:that\s+|:\s*|,\s*)?",
    ]
    pats += [  # natural style: "A PET/CT study reports that X", "In a benchmark on chest X-rays, X", "According to one study, X"
        rf"^(?:a|an|the)\s+(?:[\w\-/]+\s+){{0,5}}?{_SOURCE_NOUN}\s+(?:also\s+)?{verbs}\s*(?:that\s+|:\s*|,\s*)?",
        rf"^in\s+(?:a|an|one|the)\s+(?:[\w\-/]+\s+){{0,6}}?{_SOURCE_NOUN}(?:\s+(?:on|of|with|using|across)\s+[^,]{{3,50}})?\s*,\s*",
        r"^according to\s+[^,]{3,60},\s*",
    ]
    for p in pats:
        m = re.match(p, t, flags=re.I)
        if m:
            rest = t[m.end():].strip()
            if len(rest.split()) >= 3:
                return rest[0].upper() + rest[1:]
    return t


# ------------------------------------------------------------------------------------------------------------------ fallback wording
_LOWER_START = {
    "the", "a", "an", "in", "on", "at", "for", "of", "to", "with", "by", "from", "as", "using", "training", "pre-training", "pretraining",
    "fine-tuning", "when", "if", "while", "this", "these", "those", "it", "its", "their", "there", "some", "many", "most", "all", "both", "each",
    "models", "methods", "results", "performance", "larger", "smaller", "higher", "lower", "more", "less", "increasing",
    "decreasing", "adding", "removing", "applying", "compared", "comparing", "after", "before", "under", "without", "across", "between",
    "although", "because", "since", "unlike", "like", "despite", "transformers", "networks", "systems", "approaches", "experiments",
}


def clean_claim_text(text: str) -> str:
    """Stage 4's claim wording lightly normalised for use inside a sentence: whitespace collapsed, a leading label and citation markers removed,
    final full stop removed, first letter lowercased when the first word is a plain common word (never a name or acronym)."""
    t = re.sub(r"\s+", " ", (text or "")).strip()
    t = re.sub(r"^(?:claim|finding)\s*:\s*", "", t, flags=re.I)
    t = re.sub(r"\s*\[\s*\d+(?:\s*[,;\-–]\s*\d+)*\s*\]", "", t)
    t = t.rstrip(" .;:")
    if t:
        first = re.match(r"[A-Za-z][A-Za-z\-]*", t)
        if first and first.group(0).lower() in _LOWER_START and not re.match(r"[A-Z]{2,}", t):
            t = t[0].lower() + t[1:]
    return t


def _first_ref_key(claim) -> str:
    for e in claim.evidence or []:
        if getattr(e, "relation", "supports") == "supports" and getattr(e, "ref_key", ""):
            return e.ref_key
    return ""


def _near_text(claim) -> str:
    for e in claim.evidence or []:
        if getattr(e, "relation", "") == "near_match" and getattr(e, "near_claim", None):
            return clean_claim_text(e.near_claim)
    return ""


def _supported_opener(claim) -> str:
    n = int(getattr(claim, "support_docs", 0) or 0)
    return "Several sources report that" if n >= 3 else "Two sources report that"


def fallback_sentence(job) -> str:
    """The deterministic sentence for a job whose LLM sentence failed its checks twice. It restates Stage 4's own claim wording behind the tier's
    opener, so it keeps the hedge by construction and needs no check. One claim per clause; several claims are joined with semicolons.

      single:    One study reports that <claim>; another reports that <claim>.
      partly:    One source reports that <claim>, while another makes a related point that <near claim>.
      supported: Two sources report that <claim>. (Several sources when 3+ documents.)"""
    claims = list(getattr(job, "claims", []) or [])
    tier = getattr(job, "tier", TIER_SINGLE)
    parts: list[str] = []
    seen_keys: list[str] = []
    for i, c in enumerate(claims):
        body = clean_claim_text(c.text)
        if not body:
            continue
        key = _first_ref_key(c)
        if tier == TIER_SUPPORTED:
            lead = _supported_opener(c) if i == 0 else _supported_opener(c).lower().replace(" report ", " also report ")
            parts.append(f"{lead} {body}")
        elif tier == TIER_PARTLY:
            near = _near_text(c)
            lead = "One source reports that" if i == 0 else "another source reports that"
            tail = f", while another makes a related point that {near}" if near else ", while another source makes a related but not identical point"
            parts.append(f"{lead} {body}{tail}")
        else:
            if i == 0:
                lead = "One study reports that"
            elif key and key in seen_keys:
                lead = "it also reports that"
            else:
                lead = "another reports that"
            parts.append(f"{lead} {body}")
        seen_keys.append(key)
    if not parts:
        return ""
    return "; ".join(parts) + "."


def make_fallback_sentence(job, reasons: Optional[list] = None) -> Sentence:
    """`fallback_sentence` wrapped in the shared Sentence type (origin fallback, 0 LLM attempts, the failed-check reasons kept for the audit)."""
    return Sentence(text=fallback_sentence(job), claim_ids=[c.claim_id for c in job.claims], job_id=job.job_id, tier=job.tier,
                    origin=ORIGIN_FALLBACK, attempts=0, reasons=list(reasons or []))


__all__ = ["TIER_RULES", "TIERS", "STRENGTH", "check_hedge", "fallback_sentence", "make_fallback_sentence", "hedge_level", "strength",
           "strip_attribution", "has_opener", "has_partly_marker", "clean_claim_text"]
