"""Deterministic checks of Stage 5 sentences (no model, no network, no environment switch except the word limit). The LLM writes ONE sentence for a
job and says which claim ids it used; this module decides, in plain Python, whether the sentence may enter the report. Every function returns a
list of reasons written for the retry prompt ("number '17%' is not in the cited claims"); an empty list means the sentence passed.

Why deterministic checks next to the entailment model: NLI models and judges barely notice a changed digit, a swapped name or an added "not"
(see the grounding notes), so these are checked by code:

  * ids: at least one, all from this job (and from `allowed_ids` when given);
  * no URL, no "[n]", no author-year, no "et al.", no claim id in the text (Python adds the citations);
  * no synthesis connectives ("therefore", "thus", "overall", "this suggests ..."), unless the caller allows them (the conclusion);
  * the tier's hedge wording (hedging.check_hedge) and no source count that the claims do not support;
  * numbers (normalised: 1,000 = 1k = 1000; 12.5% = 12.5 percent; ranges; "three" = 3; units must match; "one" only when it is a number),
    names and acronyms (ViT-B/16, ImageNet-1k, CNN, Transformer), negations, direction words (higher/lower), bounds (at least / up to), scope
    words (all / always / only) and derived quantities (twice / half): every one of them must be in the cited claims' text or quotes;
  * length: one sentence, at most 60 words (STAGE5_MAX_SENTENCE_WORDS).

`check_summary` does the same for the overview summary and the conclusion (compress-only text over already validated body sentences).
Known limits (see the report of the CHECK agent): a swapped LOWERCASE common word, a changed relation between two correct names, and a
reworded comparison are left to the entailment model and the judge.
"""
import os
import re
import unicodedata
from typing import Optional

from apps.api.agents.stage5_report import hedging, settings
from apps.api.agents.stage5_report.schema import TIER_PARTLY, TIER_SINGLE, TIER_SUPPORTED

DEFAULT_MAX_WORDS = 60
MIN_WORDS = 4


def max_words() -> int:
    try:
        return max(10, int(os.getenv("STAGE5_MAX_SENTENCE_WORDS", str(DEFAULT_MAX_WORDS))))
    except ValueError:
        return DEFAULT_MAX_WORDS


# ------------------------------------------------------------------------------------------------------------------ text helpers
def _clean(t: str) -> str:
    """Light normalisation (the same idea as stage4 clean_text, written here so that importing this module never imports the NLI stack)."""
    t = unicodedata.normalize("NFKC", t or "")
    t = re.sub(r"[‐‑‒–—―−]", "-", t)
    t = t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    t = re.sub(r"[   ​]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _stem(w: str) -> str:
    """Light stemming for the name/word comparison: lowercase, plural and possessive endings removed. Both sides use it, so it need not be
    linguistically right, only the same."""
    w = w.lower()
    w = re.sub(r"'s$", "", w)
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if w.endswith("sses"):
        return w[:-2]
    if len(w) > 4 and re.search(r"(?:ch|sh|x|z|s)es$", w):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def _alnum(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


# ------------------------------------------------------------------------------------------------------------------ numbers
_ONES = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
_BIG = {"hundred": 100, "thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000}
_NUMWORD_RE = re.compile(
    r"\b(?:(?P<tens>" + "|".join(_TENS) + r")(?:[-\s](?P<ones>one|two|three|four|five|six|seven|eight|nine))?"
    r"|(?P<small>" + "|".join(_ONES) + r"))(?:\s+(?P<big>hundred|thousand|million|billion))?\b", re.I)
_A_BIG_RE = re.compile(r"\ba\s+(hundred|thousand|million|billion)\b", re.I)

# "one" is also a pronoun ("one study", "no one", "one of"). It counts as a number only before a plain noun.
_ONE_NEXT_NOT_NUMBER = set("""of another can could may might must should will would shall is are was were has have had does did that which who whose whom
and or but nor to in on at for by with from as the a an this these those it its their there than then so if when where while because since per via into
over about after before between under among such only also ever never not no cannot study studies source sources paper papers document documents article
articles report reports preprint publication page team group author authors researcher researchers""".split())
_ONE_PREV_NOT_NUMBER = set("no any every each the this that which at for of in one another".split())

# the count of documents ("two sources report ...") is wording, not a measurement: it is removed before numbers and names are read
_DOC_NOUN = r"(?:study|studies|source|sources|paper|papers|document|documents|article|articles|report|reports|preprint|preprints|publication|publications)"
_DOC_COUNT_RE = re.compile(
    rf"\b(?:one|two|three|four|five|six|several|multiple|both|a single|only one|another)\s+(?:independent\s+|recent\s+|related\s+|further\s+)?{_DOC_NOUN}\b",
    re.I)

_MULT = {"thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12, "mn": 1e6, "bn": 1e9, "tn": 1e12}
_MULT_ATTACHED = {"k": 1e3, "K": 1e3, "M": 1e6, "B": 1e9}      # single letters count as multipliers only when they touch the number (1.2k, 7B)
_UNITS = {
    "%": "%", "percent": "%", "pp": "pp",
    "ms": "ms", "millisecond": "ms", "milliseconds": "ms", "s": "s", "sec": "s", "secs": "s", "second": "s", "seconds": "s",
    "us": "us", "µs": "us", "microsecond": "us", "microseconds": "us", "ns": "ns", "nanosecond": "ns", "nanoseconds": "ns",
    "min": "min", "mins": "min", "minute": "min", "minutes": "min", "h": "h", "hr": "h", "hrs": "h", "hour": "h", "hours": "h",
    "day": "day", "days": "day", "week": "week", "weeks": "week", "month": "month", "months": "month", "year": "year", "years": "year",
    "kb": "kb", "mb": "mb", "gb": "gb", "tb": "tb", "kilobyte": "kb", "kilobytes": "kb", "megabyte": "mb", "megabytes": "mb",
    "gigabyte": "gb", "gigabytes": "gb", "terabyte": "tb", "terabytes": "tb", "gib": "gb", "mib": "mb", "byte": "byte", "bytes": "byte",
    "bit": "bit", "bits": "bit",
    "hz": "hz", "khz": "khz", "mhz": "mhz", "ghz": "ghz",
    "flop": "flops", "flops": "flops", "kflops": "kflops", "mflops": "mflops", "gflops": "gflops", "tflops": "tflops", "pflops": "pflops",
    "fps": "fps", "px": "px", "pixel": "px", "pixels": "px",
    "mm": "mm", "cm": "cm", "km": "km", "kg": "kg", "mg": "mg", "db": "db", "w": "w", "watt": "w", "watts": "w", "kw": "kw",
    "x": "x", "×": "x", "times": "x", "fold": "x", "usd": "usd", "dollar": "usd", "dollars": "usd",
}
_SINGLE_LETTER_UNITS = {"s", "h", "w", "x", "×"}      # a one-letter unit only when attached to the number (5s, 3x); "5 s" is not read as a unit

_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
_SUFFIX = r"(?:\s?(?:%|[A-Za-z×µ]+(?![A-Za-z0-9])))?"
_NOT_AFTER = r"(?<![A-Za-z0-9_./\-])"          # a digit that follows a letter, '-', '/', '.' belongs to a name (ViT-B/16, ResNet-50, v2.1), not a number
_RANGE_RE = re.compile(rf"{_NOT_AFTER}(?P<a>{_NUM})(?:\s?-\s?|\s+to\s+)(?P<b>{_NUM})(?P<suf>{_SUFFIX})")
_NUM_RE = re.compile(rf"{_NOT_AFTER}(?P<neg>-\s?)?(?P<n>{_NUM})(?:[eE](?P<e>[-+]?\d+)(?![A-Za-z0-9]))?(?P<suf>{_SUFFIX})")


def _one_is_number(s: str, m: re.Match) -> bool:
    after = s[m.end():].lstrip(" -")
    nxt = re.match(r"[A-Za-z%]+", after)
    if nxt is None:
        return False
    if nxt.group(0).lower() in ("percent",) or after.startswith("%"):
        return True
    if nxt.group(0).lower() in _ONE_NEXT_NOT_NUMBER:
        return False
    before = re.search(r"([A-Za-z]+)\W*$", s[:m.start()])
    if before and before.group(1).lower() in _ONE_PREV_NOT_NUMBER:
        return False
    return True


def _numwords_to_digits(s: str) -> str:
    s = _A_BIG_RE.sub(lambda m: str(_BIG[m.group(1).lower()]), s)

    def repl(m: re.Match) -> str:
        if m.group("tens"):
            v = _TENS[m.group("tens").lower()] + (_ONES[m.group("ones").lower()] if m.group("ones") else 0)
        else:
            small = m.group("small").lower()
            if small == "one" and not m.group("big") and not _one_is_number(s, m):
                return m.group(0)
            v = _ONES[small]
        if m.group("big"):
            v *= _BIG[m.group("big").lower()]
        return str(v)
    return _NUMWORD_RE.sub(repl, s)


def _prep_numbers(text: str) -> str:
    t = _clean(text)
    t = re.sub(r"\bper\s*cent\b", "percent", t, flags=re.I)
    t = re.sub(r"\b(?:percentage|percent)\s+points?\b", "pp", t, flags=re.I)
    t = _DOC_COUNT_RE.sub("source", t)
    return _numwords_to_digits(t)


def _suffix(suf: str):
    """-> (multiplier, canonical unit) of the word after a number."""
    raw = suf or ""
    attached = not raw.startswith(" ")
    s = raw.strip()
    if not s:
        return 1.0, ""
    low = s.lower()
    if low in _MULT:
        return _MULT[low], ""
    if attached and s in _MULT_ATTACHED:
        return _MULT_ATTACHED[s], ""
    if low in _UNITS:
        if low in _SINGLE_LETTER_UNITS and not attached:
            return 1.0, ""
        return 1.0, _UNITS[low]
    return 1.0, ""


def _val(num: str, exp: Optional[str], mult: float, neg: bool = False) -> float:
    v = float(num.replace(",", ""))
    if exp:
        v *= 10 ** int(exp)
    v *= mult
    return -v if neg else v


def vkey(v: float) -> str:
    return f"{v:.9g}"


def numbers_in(text: str) -> list[tuple[float, str, str]]:
    """Numbers of a text as (value, unit, raw text): thousands separators, k/M/B and million/billion, percent spellings, ranges (both ends take
    the unit), number words (zero to nineteen, tens, 'two hundred'), units. Numbers inside names (ViT-B/16, ResNet-50, T5) are not numbers."""
    t = _prep_numbers(text)
    out: list[tuple[float, str, str]] = []

    def take_range(m: re.Match) -> str:
        mult, unit = _suffix(m.group("suf"))
        out.append((_val(m.group("a"), None, mult), unit, m.group("a")))
        out.append((_val(m.group("b"), None, mult), unit, m.group(0).strip()))
        return " "
    t = _RANGE_RE.sub(take_range, t)
    for m in _NUM_RE.finditer(t):
        mult, unit = _suffix(m.group("suf"))
        neg = bool(m.group("neg")) and not re.search(r"[\d%]\s*$", t[:m.start()])
        out.append((_val(m.group("n"), m.group("e"), mult, neg), unit, m.group(0).strip()))
    return out


# ------------------------------------------------------------------------------------------------------------------ names and acronyms
_WORD_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z][A-Za-z0-9]*(?:[-/_.][A-Za-z0-9]+)*")
_FUNCTION_CAPS = set("""a an the one two three four five six several some many both another other this these those it its in on for according while although
whereas however meanwhile and but or so then thus""".split())


def _part_kind(p: str) -> str:
    if re.fullmatch(r"[A-Z]{2,}s?", p):
        return "acronym"
    if re.search(r"[a-z][A-Z]", p):
        return "camel"
    if re.search(r"[A-Za-z]", p) and re.search(r"\d", p):
        return "alnum"
    if re.fullmatch(r"[A-Z][a-z]+", p):
        return "cap"
    return ""


def entities_in(text: str) -> list[tuple[str, str, str]]:
    """Names in a sentence as (kind, key, raw): alphanumeric names (ViT-B/16, ImageNet-1k, T5, top-5), camelCase names (DeBERTa), acronyms (CNN,
    GPU, CNNs) and capitalised words that are not the first word of the sentence (Transformer, Google). The first word is skipped unless it is an
    acronym or alphanumeric name, because every sentence starts with a capital."""
    t = _clean(text)
    t = _DOC_COUNT_RE.sub("source", t)
    t = re.sub(r"'s\b", "", t)
    out: list[tuple[str, str, str]] = []
    lead = len(t) - len(t.lstrip())
    for m in _WORD_RE.finditer(t):
        tok = m.group(0)
        is_first = m.start() == lead
        parts = [p for p in re.split(r"[-/_.]", tok) if p]
        if any(c.isdigit() for c in tok):
            out.append(("name", _alnum(tok), tok))          # ViT-B/16 -> "vitb16": the whole token must be in the evidence
            continue
        for i, p in enumerate(parts):
            kind = _part_kind(p)
            if not kind:
                continue
            if kind == "cap" and ((is_first and i == 0) or p.lower() in _FUNCTION_CAPS):
                continue
            if kind == "acronym":
                out.append(("acronym", _stem(p), p))
            else:
                out.append((kind, _stem(p), p))
    return out


# ------------------------------------------------------------------------------------------------------------------ small lexicons
SOFT_NEGATIONS = frozenset({"without"})      # a summary may leave out "without X" (it loses a detail, it cannot reverse the finding); "not", "no", "never" may not be dropped
_NEG_RE = re.compile(
    r"\b(?:not|no|never|none|neither|nor|cannot|without|unable|fail|fails|failed|failing|lack|lacks|lacked|lacking|absent|absence|nobody|nothing)\b"
    r"|\b\w+n't\b", re.I)


def negations_in(text: str) -> list[str]:
    t = re.sub(r"\bnot only\b", " ", _clean(text), flags=re.I)
    return [m.group(0).lower() for m in _NEG_RE.finditer(t)]


_UP = set("""higher highest increase increases increased increasing improve improves improved improving improvement gain gains gained better best
outperform outperforms outperformed superior faster fastest larger largest greater stronger boost boosts boosted surpass surpasses surpassed exceeds
exceeded beat beats""".split())
_DOWN = set("""lower lowest decrease decreases decreased decreasing reduce reduces reduced reducing reduction drop drops dropped decline declines declined
worse worst underperform underperforms underperformed inferior slower slowest smaller smallest weaker degrade degrades degraded degradation
loss losses lag lags lagged trail trails trailed""".split())
_SCOPE = set("""all every always never none entire entirely only most majority universally completely fully exclusively solely""".split())
_LOWER_BOUND_RE = re.compile(r"\b(?:at least|no fewer than|more than|greater than|over|above|exceeds?|exceeding)\b", re.I)
_UPPER_BOUND_RE = re.compile(r"\b(?:up to|at most|no more than|less than|fewer than|under|below)\b", re.I)
_LOWER_BOUND_NUM_RE = re.compile(r"\b(?:at least|no fewer than|more than|greater than|over|above|exceeds?|exceeding)\s+(?:about\s+|roughly\s+)?[$~]?\d", re.I)
_UPPER_BOUND_NUM_RE = re.compile(r"\b(?:up to|at most|no more than|less than|fewer than|under|below)\s+(?:about\s+|roughly\s+)?[$~]?\d", re.I)
_QTY_GROUPS = [{"twice", "double", "doubled", "twofold", "doubling"}, {"half", "halved", "halves", "halving"}, {"triple", "tripled", "threefold", "thrice"}]


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z][a-z'\-]*", _clean(text).lower())


class _Evidence:
    """What the cited claims (and quotes) contain, in the forms the checks compare."""

    def __init__(self, primary: list, quotes: list):
        self.primary = " ".join(x for x in primary if x)
        self.all_text = " ".join(x for x in list(primary) + list(quotes) if x)
        nums = numbers_in(self.all_text)
        self.num_values = {vkey(v) for v, _, _ in nums}
        self.num_pairs = {(vkey(v), u) for v, u, _ in nums}
        t = _clean(self.all_text)
        t = re.sub(r"'s\b", "", t)
        toks = [m.group(0) for m in _WORD_RE.finditer(t)]
        self.words = {_stem(w) for w in re.findall(r"[A-Za-z0-9]+", t)}
        self.raw_words = set(_words(self.all_text))
        keys: set[str] = set()
        for tok in toks:
            keys.add(_alnum(tok))
            parts = [p for p in re.split(r"[-/_.]", tok) if p]
            for i in range(len(parts)):                            # every contiguous run of parts: ViT-B/16 -> vit, vitb, vitb16, b, b16, 16
                for j in range(i + 1, len(parts) + 1):
                    keys.add(_alnum("".join(parts[i:j])))
        allw = re.findall(r"[A-Za-z0-9]+(?:[-/_.][A-Za-z0-9]+)*", t)
        for i in range(len(allw) - 1):                             # "ViT B/16" or "top 1" written with a space
            keys.add(_alnum(allw[i] + allw[i + 1]))
            if i + 2 < len(allw):
                keys.add(_alnum(allw[i] + allw[i + 1] + allw[i + 2]))
        self.name_keys = keys
        self.neg_primary = negations_in(self.primary)
        self.neg_all = negations_in(self.all_text)


def _grounding_problems(text: str, ev: _Evidence, *, where: str = "the cited claims", soft_drops: bool = False) -> list[str]:
    """Numbers, names, negations, directions, bounds, scope words and derived quantities of `text` that `ev` does not contain."""
    reasons: list[str] = []
    seen: set[str] = set()

    def add(r: str) -> None:
        if r not in seen:
            seen.add(r)
            reasons.append(r)

    for v, u, raw in numbers_in(text):
        k = vkey(v)
        ok = (k in ev.num_values) if not u else ((k, u) in ev.num_pairs)
        if not ok:
            if u and k in ev.num_values:
                add(f"number '{raw}' has a unit ('{u}') that {where} do not give it")
            else:
                add(f"number '{raw}' is not in {where} (do not compute, round or add numbers)")
    for kind, key, raw in entities_in(text):
        if kind == "name":
            ok = key in ev.name_keys
        else:
            ok = key in ev.words or key in ev.name_keys
        if not ok:
            add(f"name '{raw}' is not in {where}")
    neg_s = negations_in(text)
    if neg_s and not ev.neg_primary:
        add(f"negation '{neg_s[0]}' is not in the wording of {where}")
    hard_neg = [n for n in ev.neg_primary if not (soft_drops and n in SOFT_NEGATIONS)]
    if hard_neg and not neg_s:
        add(f"{where} contain a negation ('{hard_neg[0]}') that the sentence drops")
    words = set(_words(text))
    for pole, other, label in ((_UP, _DOWN, "an increase/advantage"), (_DOWN, _UP, "a decrease/disadvantage")):
        if words & pole and not (ev.raw_words & pole) and (ev.raw_words & other):
            add(f"direction word '{sorted(words & pole)[0]}' reverses the direction in {where}")
    for w in sorted(words & _SCOPE):
        if w not in ev.raw_words and not (w == "never" and ev.neg_all):
            add(f"scope word '{w}' is not in {where} (do not generalise)")
    for group in _QTY_GROUPS:
        hit = words & group
        if hit and not (ev.raw_words & group):
            add(f"derived quantity '{sorted(hit)[0]}' is not in {where}")
    t = _clean(text)
    if _LOWER_BOUND_NUM_RE.search(t) and not _LOWER_BOUND_RE.search(ev.all_text):
        add(f"the lower bound ('{_LOWER_BOUND_NUM_RE.search(t).group(0).split()[0]} ...') is not in {where}")
    if _UPPER_BOUND_NUM_RE.search(t) and not _UPPER_BOUND_RE.search(ev.all_text):
        add(f"the upper bound ('{_UPPER_BOUND_NUM_RE.search(t).group(0).split()[0]} ...') is not in {where}")
    return reasons[:8]


# ------------------------------------------------------------------------------------------------------------------ structure checks
_URL_RE = re.compile(
    r"(?:https?://|ftp://|www\.)\S+|\bdoi\s*:|\b10\.\d{4,9}/\S+|\barxiv\s*:|"
    r"\b[a-z0-9][a-z0-9\-]*\.(?:com|org|net|io|edu|gov|ai|co\.uk|ac\.uk|info|dev|app)\b", re.I)
_BRACKET_RE = re.compile(r"[\[\]]")
_CLAIM_ID_RE = re.compile(r"\bc_[0-9a-f]{6,}\b")
_AUTHOR_YEAR_RES = [
    re.compile(r"\(\s*[A-Z][\w'\-]+(?:\s+(?:et al\.?|and|&)\s*[A-Z]?[\w'\-]*)?\s*,?\s*(?:19|20)\d{2}[a-z]?\s*\)"),
    re.compile(r"\bet al\b\.?", re.I),
    re.compile(r"\b[A-Z][a-z]+\s+(?:and|&)\s+[A-Z][a-z]+\s*[\(,]\s*(?:19|20)\d{2}"),
    re.compile(r"\b[A-Z][a-z]+\s*\(\s*(?:19|20)\d{2}[a-z]?\s*\)"),
]
_CONNECTIVE_RE = re.compile(
    r"\b(?:therefore|thus|hence|consequently|accordingly|as a result|overall|in general|in conclusion|in summary|to summari[sz]e|all in all|"
    r"taken together|taken as a whole|collectively|this suggests|these (?:results|findings|studies|data) (?:suggest|imply|indicate)|"
    r"which (?:suggests|implies|means|indicates|shows)|suggesting that|implying that|this (?:implies|means|indicates|shows|demonstrates)|"
    r"it follows|by extension|on the whole|broadly speaking)\b", re.I)
_INITIAL_CONNECTIVE_RE = re.compile(r"^\W*(?:however|moreover|furthermore|additionally|in addition|similarly|likewise|conversely|by contrast|meanwhile|also|but|and|so)\b", re.I)
_FORMAT_RE = re.compile(r"[\n\r\t]|\*\*|`|^\s*(?:[-*•#]|\d+[.)])\s")
_ABBREV_RE = re.compile(r"\b(?:e\.g|i\.e|vs|etc|fig|eq|approx|cf|resp|no|al)\.", re.I)


def count_sentences(text: str) -> int:
    t = _ABBREV_RE.sub(lambda m: m.group(0).replace(".", ""), text.strip())
    t = re.sub(r"(?<=\d)\.(?=\d)", "", t)
    parts = re.split(r"[.!?]+(?=\s+[A-Z\"'(])", t)
    return len([p for p in parts if p.strip(" .!?")])


def citation_problems(text: str) -> list[str]:
    """URL, [n], author-year, 'et al.', claim id in text the LLM wrote (Python adds every citation)."""
    reasons = []
    if _URL_RE.search(text):
        reasons.append("contains a URL, DOI or arXiv id (do not write links; citations are added by the system)")
    if _BRACKET_RE.search(text):
        reasons.append("contains square brackets (do not write [n] markers; citations are added by the system)")
    if _CLAIM_ID_RE.search(text):
        reasons.append("contains a claim id (ids go in claim_ids, not in the text)")
    if any(r.search(text) for r in _AUTHOR_YEAR_RES):
        reasons.append("contains an author name with a year or 'et al.' (do not name authors or years)")
    return reasons


def connective_problems(text: str, tolerated: str = "") -> list[str]:
    reasons = []
    tol = (tolerated or "").lower()
    for m in _CONNECTIVE_RE.finditer(text):
        if m.group(0).lower() not in tol:
            reasons.append(f"synthesis wording '{m.group(0).lower()}' is not allowed (state only what the claims say)")
            break
    m = _INITIAL_CONNECTIVE_RE.match(text)
    if m and m.group(0).strip(" ,.").lower() not in tol:
        reasons.append(f"the sentence must stand alone: do not start with '{m.group(0).strip(' ,.')}'")
    return reasons


def shape_problems(text: str) -> list[str]:
    reasons = []
    n = len(text.split())
    if n < MIN_WORDS:
        reasons.append(f"too short ({n} words)")
    if n > max_words():
        reasons.append(f"too long ({n} words; at most {max_words()}): shorten it to about {max(10, max_words() - 10)} words by leaving out the least important detail")
    if _FORMAT_RE.search(text):
        reasons.append("contains formatting (newline, bullet, bold or backticks); write one plain sentence")
    if count_sentences(text) > 1:
        reasons.append("must be exactly one sentence")
    return reasons


_COUNT_WORD = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
_SOURCE_COUNT_RE = re.compile(rf"\b(two|three|four|five|six)\s+(?:independent\s+)?{_DOC_NOUN}\b", re.I)


def source_count_problems(tier: str, text: str, claims: list) -> list[str]:
    """'Three sources report' needs three supporting documents in the cited claims."""
    if tier != TIER_SUPPORTED:
        return []
    docs = max([int(getattr(c, "support_docs", 0) or 0) for c in claims] or [0])
    if docs <= 0:
        return []
    for m in _SOURCE_COUNT_RE.finditer(text):
        if _COUNT_WORD[m.group(1).lower()] > docs:
            return [f"'{m.group(0)}' names more documents than support the claim ({docs})"]
    return []


# ------------------------------------------------------------------------------------------------------------------ claim evidence
def _claims_of(job_or_claims) -> list:
    return list(getattr(job_or_claims, "claims", job_or_claims) or [])


def primary_texts(claims) -> list[str]:
    """The claim wordings (and, for partly claims, the other document's own wording)."""
    out = []
    for c in _claims_of(claims):
        out.append(c.text or "")
        out.extend(e.near_claim for e in (c.evidence or []) if getattr(e, "near_claim", None))
    return out


def quote_texts(claims) -> list[str]:
    out = []
    for c in _claims_of(claims):
        out.extend(e.quote for e in (c.evidence or []) if e.quote and getattr(e, "relation", "supports") in ("supports", "near_match"))
    return out


def evidence_texts(job_or_claims, claim_ids=None) -> list[str]:
    """The texts the entailment check uses as premises: the claim wordings first, then the quotes (the order matters when a long concatenation is
    cut by the model's window). `claim_ids` limits it to the cited claims."""
    claims = _claims_of(job_or_claims)
    if claim_ids:
        picked = [c for c in claims if c.claim_id in set(claim_ids)]
        claims = picked or claims
    seen, out = set(), []
    for t in primary_texts(claims) + quote_texts(claims):
        t = _clean(t)
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


# ------------------------------------------------------------------------------------------------------------------ the sentence check
def check_sentence(text, claim_ids, job, *, allowed_ids=None) -> list[str]:
    """Reasons why the LLM sentence may not enter the report (empty list = it passed). `claim_ids` are the ids the LLM says it used; they must be
    from `job` (and from `allowed_ids` when given) and at least one. The numbers, names and so on are compared with the CITED claims only, so a
    figure taken from an uncited claim is caught as well."""
    if not isinstance(text, str) or not text.strip():
        return ["empty sentence"]
    text = text.strip()
    reasons: list[str] = []
    ids = list(claim_ids) if isinstance(claim_ids, (list, tuple, set)) else []
    job_claims = _claims_of(job)
    job_ids = {c.claim_id for c in job_claims}
    if not ids:
        reasons.append("no claim id given (list the ids of the claims the sentence uses)")
    foreign = [i for i in ids if i not in job_ids]
    if foreign:
        reasons.append(f"claim id(s) {', '.join(map(str, foreign))} do not belong to this sentence job")
    if allowed_ids is not None:
        extra = [i for i in ids if i in job_ids and i not in set(allowed_ids)]
        if extra:
            reasons.append(f"claim id(s) {', '.join(map(str, extra))} are not allowed here")
    reasons += shape_problems(text)
    reasons += citation_problems(text)
    cited = [c for c in job_claims if c.claim_id in set(ids)]
    primary = primary_texts(cited)
    reasons += connective_problems(text, " ".join(primary))
    tier = getattr(job, "tier", TIER_SINGLE)
    reasons += hedging.check_hedge(tier, text, " ".join(primary))
    reasons += source_count_problems(tier, text, cited)
    if cited:
        reasons += _grounding_problems(text, _Evidence(primary, quote_texts(cited)))
    return reasons


# ------------------------------------------------------------------------------------------------------------------ summary / conclusion
def _get(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _body_text(b) -> str:
    return b if isinstance(b, str) else str(_get(b, "text", "") or "")


def _body_strength(b) -> int:
    return hedging.strength(None if isinstance(b, str) else _get(b, "tier"), _body_text(b))


def check_summary(summary_sentences, body_sentences, *, min_sentences: int = 3, max_sentences: int = 5, allow_connectives: bool = False,
                  index_base: int = 1) -> list[str]:
    """Reasons why a summary (or conclusion) may not be used (empty = fine). `summary_sentences`: [{"text", "from_sentences": [n, ...]}] (or
    objects with those attributes); `body_sentences`: the validated body sentences (dicts, Sentence objects or plain strings; the tier is read from
    `tier` when present, otherwise from the wording). `from_sentences` numbers body sentences from `index_base` (1 = as the prompt lists them).

    Rules: min..max sentences (the minimum is lowered to the number of body sentences when the body is shorter); every sentence is one sentence of
    at most 60 words, with no URL / [n] / author-year; every sentence maps to at least one existing body sentence; every number, name, negation,
    direction, bound and scope word of it appears in the sentences it maps to; its hedge is not stronger than the weakest mapped sentence;
    synthesis connectives are rejected unless `allow_connectives` (the conclusion)."""
    reasons: list[str] = []
    sums = list(summary_sentences or [])
    body = list(body_sentences or [])
    lo = min(min_sentences, len(body)) if body else 0
    if not body:
        return ["there are no validated body sentences to summarise"]
    if len(sums) < lo or len(sums) > max_sentences:
        reasons.append(f"must have {lo} to {max_sentences} sentences, has {len(sums)}")
    for n, s in enumerate(sums, 1):
        pre = f"sentence {n}: "
        text = _get(s, "text", "") or ""
        if not isinstance(text, str) or not text.strip():
            reasons.append(pre + "empty")
            continue
        text = text.strip()
        local = shape_problems(text) + citation_problems(text)
        raw_map = _get(s, "from_sentences", None)
        idx: list[int] = []
        bad = False
        for x in (raw_map if isinstance(raw_map, (list, tuple)) else []):
            try:
                i = int(x) - index_base
            except (TypeError, ValueError):
                bad = True
                continue
            if 0 <= i < len(body):
                if i not in idx:
                    idx.append(i)
            else:
                bad = True
        if not idx:
            local.append("from_sentences must list the numbers of the body sentences it summarises")
        elif bad:
            local.append("from_sentences contains a number that is not a body sentence")
        mapped = [body[i] for i in idx]
        if not allow_connectives:
            local += connective_problems(text, " ".join(_body_text(b) for b in mapped))
        if mapped:
            ev = _Evidence([_body_text(b) for b in mapped], [])
            local += _grounding_problems(text, ev, where="the body sentences it summarises", soft_drops=True)
            weakest = min(_body_strength(b) for b in mapped)
            if settings.natural():
                problem = hedging.natural_summary_problem({1: "single", 2: "partly", 3: "supported"}[weakest], text)
                if problem:
                    local.append(problem)
            elif hedging.strength(None, text) > weakest:
                name = {1: "single-source", 2: "partly supported", 3: "supported"}[weakest]
                local.append(f"its wording is stronger than the weakest sentence it summarises ({name}); keep the hedge ('One study reports ...')")
        reasons += [pre + r for r in local]
    return reasons


__all__ = ["check_sentence", "check_summary", "numbers_in", "entities_in", "negations_in", "evidence_texts", "primary_texts", "quote_texts",
           "citation_problems", "connective_problems", "shape_problems", "count_sentences", "max_words"]
