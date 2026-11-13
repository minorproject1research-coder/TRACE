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

from apps.api.agents.stage5_report.schema import ORIGIN_TEMPLATE, Sentence

STOPWORDS = frozenset("""a an and are as at be by can could do does for from has have how in into is it its of on or than that the their there these this to was were what when
which who whom why will with would about across between compared compare versus vs other over under using use used based""".split())
TIER_RANK = {"supported": 3, "partly": 2, "single": 1}
TOP_SECTIONS = 4                    # sections whose sentences feed the answer
REQUIRED_SECTIONS = 3               # the answer must use at least this many of the top sections (fewer when the report has fewer)
PER_TOP_SECTION = 4                 # sentences taken from each of the top sections for the answer
TIER_NOTE = "note"                  # a template note without a source: no tier label is shown for it
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


BOILERPLATE = frozenset("one source sources study studies report reports reported another makes make related point two several according say says".split())
DUPLICATE_JACCARD = 0.6


def content_tokens(text: str) -> set:
    """The words of a sentence that carry its finding (the attribution wording of the tiers removed)."""
    return tokens(text) - {_stem(w) for w in BOILERPLATE} - BOILERPLATE


def dedupe_section(sentences: list) -> tuple:
    """(kept, dropped): sentences of ONE section that say nearly the same as a stronger or earlier one are left out (7 sentences "heterogeneity degrades
    performance" in run 37). The stronger tier wins, then the model's wording over a fallback, then the earlier sentence; the kept ones keep their order."""
    order = sorted(range(len(sentences)), key=lambda i: (-TIER_RANK.get(sentences[i].tier, 0), sentences[i].origin != "llm", i))
    kept_idx, seen = [], []
    for i in order:
        tk = content_tokens(sentences[i].text)
        if any(_near_duplicate_at(tk, o, DUPLICATE_JACCARD) for o in seen):
            continue
        seen.append(tk)
        kept_idx.append(i)
    keep = set(kept_idx)
    return [s for i, s in enumerate(sentences) if i in keep], [s for i, s in enumerate(sentences) if i not in keep]


def _near_duplicate_at(a: set, b: set, level: float) -> bool:
    return bool(a and b) and len(a & b) / len(a | b) >= level


def _sentence_rank(s: Sentence, q_tokens: set) -> tuple:
    """Better first: stronger tier, has a figure, shares more words with the question."""
    has_figure = bool(re.search(r"\d", s.text))
    return (-TIER_RANK.get(s.tier, 0), -int(has_figure), -len(tokens(s.text) & q_tokens))


def _near_duplicate(a: set, b: set) -> bool:
    return bool(a and b) and len(a & b) / len(a | b) >= 0.55


def candidates(question: str, sections: list, sentences_by_section: list, limit: int = 16, per_section: int = PER_TOP_SECTION) -> tuple:
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


BACKGROUND_TITLE = re.compile(r"^\s*(how|where)\s+(is|are|can|do|does)\b.*\b(applied|used|utili[sz]ed|deployed)\b|\b(applications?|datasets?|use cases?)\b", re.I)


def make_embedder():
    """texts -> normalised vectors with the bge model of Stage 2 (loaded once, shared); None when it cannot be loaded."""
    try:
        from apps.api.agents.stage2_retrieval.relevance_filter import get_embedder
        model = get_embedder()
        return lambda texts: model.encode(list(texts), normalize_embeddings=True)
    except Exception:
        return None


PART_MIN = 3                        # the answer is built part by part when at least this many sections qualify
MAX_PARTS = 5                       # the planner now writes up to 5 sub-questions that are all about the answer; background ones fall below MIN_PART_RELEVANCE
MIN_PART_RELEVANCE = 0.3            # a section is a part when its relevance to the question is at least this share of the best section's
PER_PART = 1                        # sentences offered to the model for each part


def select_parts(question: str, sections: list, sentences_by_section: list, max_parts: int = MAX_PARTS, per_part: int = PER_PART, embed=None) -> list:
    """[(section index, [Sentence, ...])], the most relevant sections first, with the sentences of each part that the answer may use: the ones whose finding
    words are closest to the question and the section's own title (words that few sentences share count most, so "privacy-utility trade-off" beats
    "federated learning"), then the stronger tier, then those with a figure; no two near duplicates. The model only words ONE sentence per part from them."""
    q = tokens(question)
    top = top_sections(question, sections, sentences_by_section, k=max_parts)
    scores = section_scores(question, sections)
    best = max((scores[i] for i in top), default=0.0)
    top = [i for i in top if scores[i] >= MIN_PART_RELEVANCE * best]
    foreground = [i for i in top if not BACKGROUND_TITLE.search(sections[i].title)]
    if len(foreground) >= PART_MIN:
        top = foreground                                # "where is X applied / which datasets" describes use, not how well it works or what it costs
    qv = None
    if embed is not None:
        try:
            qv = embed([question])[0]
        except Exception:
            embed = None
    everything = [s for ss in sentences_by_section for s in ss]
    df: dict = {}
    for s in everything:
        for w in tokens(s.text):
            df[w] = df.get(w, 0) + 1
    total = max(1, len(everything))

    def weight(w: str) -> float:
        return 1.0 - df.get(w, 0) / total

    parts = []
    for i in top:
        focus = q | tokens(sections[i].title)
        by_meaning = None
        if embed is not None:
            try:
                vecs = embed([f"{sections[i].title} {' '.join(getattr(sections[i], 'detail_questions', None) or [])}"] + [s.text for s in sentences_by_section[i]])
                by_meaning = {id(s): float(vecs[k + 1] @ qv) + float(vecs[k + 1] @ vecs[0]) for k, s in enumerate(sentences_by_section[i])}
            except Exception:
                by_meaning = None
        if by_meaning is not None:
            ranked = sorted(sentences_by_section[i], key=lambda s: (-round(by_meaning[id(s)] + 0.02 * TIER_RANK.get(s.tier, 0), 3), -int(bool(re.search(r"\d", s.text)))))
        else:
            ranked = sorted(sentences_by_section[i], key=lambda s: (-sum(weight(w) for w in tokens(s.text) & focus), -TIER_RANK.get(s.tier, 0), -int(bool(re.search(r"\d", s.text)))))
        chosen, seen = [], []
        for s in ranked:
            tk = content_tokens(s.text)
            if any(_near_duplicate_at(tk, o, 0.5) for o in seen):
                continue
            seen.append(tk)
            chosen.append(s)
            if len(chosen) >= per_part:
                break
        if chosen:
            parts.append((i, chosen))
    return parts


def part_problems(items: list, body: list, parts: list, titles: dict, require_all: bool = True) -> list:
    """Reasons when the answer is not one sentence per part: a sentence mixing sentences of different parts, two sentences for one part, a part left out
    (not asked when `require_all` is False: salvaging an answer keeps what passed). "sentence k: ..." reasons can be salvaged by dropping that sentence."""
    section_of = {b["n"]: b.get("section") for b in body}
    out, seen = [], set()
    for k, it in enumerate(items, start=1):
        in_parts = {section_of.get(n) for n in it.get("from_sentences", [])}
        if len(in_parts) != 1 or next(iter(in_parts)) not in parts:
            out.append(f"sentence {k}: it must be based only on the numbered sentences under ONE Part header (do not mix parts)")
        elif next(iter(in_parts)) in seen:
            out.append(f"sentence {k}: this part already has its sentence; write exactly one sentence per part")
        else:
            seen.add(next(iter(in_parts)))
    if require_all:
        for i in parts:
            if i not in seen:
                out.append(f"the answer has no sentence for the part \"{titles.get(i, i)}\"; write one sentence for every part")
    return out


def order_items(items: list, body: list, order: list) -> list:
    """The answer sentences in the order of the parts (the most relevant part first), whatever order the model wrote them in."""
    section_of = {b["n"]: b.get("section") for b in body}
    rank = {i: r for r, i in enumerate(order or [])}
    return sorted(items, key=lambda it: min((rank.get(section_of.get(n), 99) for n in it.get("from_sentences", [])), default=99))


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
    return Sentence(text=text, claim_ids=[], job_id="answer_gaps", tier=TIER_NOTE, origin=ORIGIN_TEMPLATE, attempts=0)
