"""The ANSWER of Stage 5 (template s5-v2): what goes into the executive summary so that it answers the question that was asked.

Python decides, deterministically, with no model:
  - which sections matter for the question: a section is scored by how many words of the question its title (and detail questions) share. Background
    sections ("what is X", "what are the datasets") share few and come last;
  - which validated sentences the answer may use: the best sentences of the most relevant sections, figures first, every one of the top sections
    represented; the next-ranked ones go to the conclusion;
  - whether an answer is acceptable: it must draw on at least `required` of the top sections (a coverage check) on top of the usual checks
    (numbers, names, hedge strength, length), otherwise it is rejected with the name of the part it left out;
  - the note about what the evidence does not settle: a template sentence from Stage 3's gap data of the top sections (no model, no citation).

The model only words the answer from the numbered sentences (summary.py, prompts.ANSWER_SYSTEM).
"""
import re
from typing import Optional

from apps.api.agents.stage5_report.schema import ORIGIN_TEMPLATE, TIER_SINGLE, Sentence

STOPWORDS = frozenset("""a an and are as at be by can could do does for from has have how in into is it its of on or than that the their there these this to was were what when
which who whom why will with would about across between compared compare versus vs other over under using use used based""".split())
TIER_RANK = {"supported": 3, "partly": 2, "single": 1}
TOP_SECTIONS = 3                    # sections whose sentences feed the answer
REQUIRED_SECTIONS = 2               # the answer must use at least this many of the top sections (fewer when the report has fewer)
PER_TOP_SECTION = 5                 # sentences taken from each of the top sections for the answer
GAP_PREFIX = "The collected evidence does not sufficiently answer: "


def _stem(w: str) -> str:
    for suf in ("ations", "ation", "ings", "ing", "ies", "es", "ed", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def tokens(text: str) -> set:
    """Content words of a text, stemmed; hyphenated words give the whole word and its parts (trade-off, trade, off); Unicode hyphens count as hyphens."""
    t = re.sub(r"[‐-―−]", "-", (text or "").lower())
    out = set()
    for w in re.findall(r"[a-z][a-z0-9\-]+", t):
        parts = [p for p in w.split("-") if p]
        for x in [w.strip("-")] + (parts if len(parts) > 1 else []):
            if x not in STOPWORDS and len(x) > 2:
                out.add(_stem(x))
    return out


def section_scores(question: str, sections: list) -> list:
    """[score] per section: the share of the section title's content words that are in the question, plus how many question words it covers.
    `sections`: objects (or dicts) with `title` and `detail_questions`."""
    q = tokens(question)
    out = []
    for s in sections:
        title = s.get("title") if isinstance(s, dict) else getattr(s, "title", "")
        t = tokens(title)
        if not t or not q:
            out.append(0.0)
            continue
        shared = t & q
        out.append(len(shared) / len(t) + 0.15 * len(shared))
    return out


def top_sections(question: str, sections: list, sentences_by_section: list, k: int = TOP_SECTIONS) -> list:
    """The indexes of the k most relevant sections that have sentences, best first (ties: later section first, the planner puts the question itself last)."""
    scores = section_scores(question, sections)
    order = sorted((i for i in range(len(sections)) if sentences_by_section[i]), key=lambda i: (-scores[i], -i))
    return order[:k]


def _sentence_rank(s: Sentence, q_tokens: set) -> tuple:
    """Better first: stronger tier, has a figure, shares more words with the question."""
    has_figure = bool(re.search(r"\d", s.text))
    return (-TIER_RANK.get(s.tier, 0), -int(has_figure), -len(tokens(s.text) & q_tokens))


def _near_duplicate(a: set, b: set) -> bool:
    return bool(a and b) and len(a & b) / len(a | b) >= 0.55


def candidates(question: str, sections: list, sentences_by_section: list, limit: int = 14, per_section: int = PER_TOP_SECTION) -> tuple:
    """(answer_candidates, conclusion_candidates, top_indexes). The answer candidates are the best `per_section` sentences of each of the top sections,
    then the best of the other sections up to `limit`; the conclusion candidates are the next-ranked sentences of the top sections (not in the answer)."""
    q = tokens(question)
    top = top_sections(question, sections, sentences_by_section)
    chosen: list = []
    seen: list = []

    def take(s) -> bool:
        tk = tokens(s.text)
        if any(_near_duplicate(tk, o) for o in seen):
            return False                                    # the same finding worded twice: one is enough for the answer
        seen.append(tk)
        chosen.append(s)
        return True

    for i in top:
        got = 0
        for s in sorted(sentences_by_section[i], key=lambda s: _sentence_rank(s, q)):
            if got >= per_section:
                break
            got += take(s)
    rest = [s for i, ss in enumerate(sentences_by_section) if i not in top for s in ss]
    for s in sorted(rest, key=lambda s: _sentence_rank(s, q)):
        if len(chosen) >= limit:
            break
        take(s)
    chosen = chosen[:limit]
    used = {id(s) for s in chosen}
    spare = [s for i in top for s in sorted(sentences_by_section[i], key=lambda s: _sentence_rank(s, q)) if id(s) not in used]
    return chosen, spare[:limit], top


def coverage_problems(items: list, body: list, required_sections: list, titles: dict) -> list:
    """Reasons when the answer does not draw on enough of the required sections. `items`: [{"from_sentences": [n]}]; `body`: dicts with "n" and "section"
    (an index, set by the assembler); `required_sections`: indexes the answer must touch at least REQUIRED_SECTIONS of; `titles`: index -> title."""
    if not required_sections:
        return []
    section_of = {b["n"]: b.get("section") for b in body}
    touched = {section_of.get(n) for it in items for n in it.get("from_sentences", [])}
    need = min(REQUIRED_SECTIONS, len(required_sections))
    present = [i for i in required_sections if i in touched]
    if len(present) >= need:
        return []
    missing = [i for i in required_sections if i not in touched]
    names = "; ".join(f"\"{titles.get(i, i)}\" (sentences {[b['n'] for b in body if b.get('section') == i][:6]})" for i in missing[:2])
    return [f"the answer must also draw on the part of the report about {names}"]


def gap_sentence(gaps_of_top_sections: list) -> Optional[Sentence]:
    """One template sentence: what the evidence does not settle, from the gap lines "The collected evidence does not sufficiently answer: ..."
    of the top sections (the aspects named there, at most 3). None when there is nothing to say."""
    aspects: list = []
    for gaps in gaps_of_top_sections:
        for g in gaps or []:
            if str(g).startswith(GAP_PREFIX):
                aspects += [a.strip().rstrip(".") for a in str(g)[len(GAP_PREFIX):].split(";") if a.strip()]
    aspects = list(dict.fromkeys(aspects))[:3]
    if not aspects:
        return None
    aspects = [a.rstrip("?. ") for a in aspects]
    text = "The evidence collected does not settle: " + "; ".join(a[:1].lower() + a[1:] if not a[:2].isupper() else a for a in aspects) + "."
    return Sentence(text=text, claim_ids=[], job_id="answer_gaps", tier=TIER_SINGLE, origin=ORIGIN_TEMPLATE, attempts=0)
