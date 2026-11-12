"""Which claims Stage 5 may write about, and with which wording tier. Pure Python, no I/O, no model (the optional scope check is injectable).

The Stage 4 label never changes; the TIER only decides the wording of the sentence (see schema.TIERS):
  supported            label supported, not contested            "Two sources report ..."
  partly               label partially_supported, not contested  "[A] reports X; [B] makes a related point"
  single               label unverified, not contested           "One study reports ..." (attributed, never as fact), after the filters below
  disputed             label contradicted, or contested=True     never in the prose; shown in "Sources disagree" (disputed_for_section)
A claim that is filtered out keeps its label, gets tier None and a `filtered_reason`, and is counted in the gaps of the report.

Filters for the single tier (switches read at CALL time, defaults in brackets):
  STAGE5_SINGLE_NEEDS_STRONG (true)  the supporting evidence must be full text, or via == "stage3_judge" (the Stage 3 judge confirmed it)
  STAGE5_SCOPE_CHECK (false)         the claim must not be broader than its quote (NLI quote -> claim; needs the NLI model, so off by default)
  STAGE5_MAX_PER_SOURCE (3)          at most this many single claims from one document in the whole report (best first: full text, confidence)
  STAGE5_MAX_SINGLE_PER_SECTION (8)  at most this many single claims per section, preferring different documents (best claim of each document
                                     first, then the second best of each, ...). A value below 1 switches a cap off.

Claim ids come from schema.make_claim_id (sub-question id + claim text), so they are the same on every rerun of Stage 4.
The links between the contradictions table and the claims are made by TEXT here (the table has no ids): see disputed_for_section.
"""
import hashlib
import os
import re
from typing import Callable, Optional

from apps.api.agents.stage5_report.references import LEVEL_RANK, ref_key_of
from apps.api.agents.stage5_report.schema import (Claim, Disagreement, Evidence, Job, TIER_DISPUTED, TIER_PARTLY, TIER_SINGLE, TIER_SUPPORTED,
                                                  TIERS, make_claim_id)

# Stage 4 labels (never changed here)
LABEL_SUPPORTED, LABEL_PARTLY, LABEL_UNVERIFIED, LABEL_CONTRADICTED = "supported", "partially_supported", "unverified", "contradicted"
LABEL_TIER = {LABEL_SUPPORTED: TIER_SUPPORTED, LABEL_PARTLY: TIER_PARTLY, LABEL_UNVERIFIED: TIER_SINGLE}
WRITABLE_TIERS = (TIER_SUPPORTED, TIER_PARTLY, TIER_SINGLE)       # tiers that get sentences, in the order of the report

# Why a claim is not written about
FILTER_WEAK = "weak_evidence"            # single: the quote is from an abstract or a web snippet and Stage 3 did not confirm it
FILTER_SCOPE = "scope"                   # single: the claim says more than its quote (or the scope check failed)
FILTER_SOURCE_CAP = "per_source_cap"     # single: that document already has STAGE5_MAX_PER_SOURCE claims
FILTER_SECTION_CAP = "section_cap"       # single: the section already has STAGE5_MAX_SINGLE_PER_SECTION single claims
FILTER_INCOMPLETE = "incomplete_evidence"        # the evidence does not fit the label (no quote, one document under "supported", no near-match under "partly")
FILTER_UNKNOWN = "unknown_label"
FILTER_MIRROR = "mirror_pair"            # partly: the same two statements were already reported the other way round (A near B, then B near A)
FILTER_REASONS = (FILTER_WEAK, FILTER_SCOPE, FILTER_SOURCE_CAP, FILTER_SECTION_CAP, FILTER_INCOMPLETE, FILTER_UNKNOWN, FILTER_MIRROR)

DEFAULT_MAX_PER_SOURCE = 3
DEFAULT_MAX_SINGLE_PER_SECTION = 8
DEFAULT_SCOPE_ENTAIL_MIN = 0.5
STRONG_VIA = "stage3_judge"
MAX_PER_JOB = 3
PARTLY_PER_JOB = 1      # a partly sentence carries the claim AND the other document's related wording: three of them cannot fit in 60 words (first live run)


# ----------------------------------------------------------------------------------------------------------------------- settings
def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "").strip().lower()
    return default if not raw else raw in ("1", "true", "yes", "on")


def max_per_source() -> int:
    return _env_int("STAGE5_MAX_PER_SOURCE", DEFAULT_MAX_PER_SOURCE)


def max_single_per_section() -> int:
    return _env_int("STAGE5_MAX_SINGLE_PER_SECTION", DEFAULT_MAX_SINGLE_PER_SECTION)


def single_needs_strong() -> bool:
    return _env_bool("STAGE5_SINGLE_NEEDS_STRONG", True)


def scope_check_enabled() -> bool:
    return _env_bool("STAGE5_SCOPE_CHECK", False)


def default_scope_check(claim_text: str, quote: str) -> bool:
    """True when the quote entails the claim (so the claim is not broader than its quote). Uses Stage 4's NLI model, loaded only when called;
    any error is "not entailed" (fail closed)."""
    try:
        from apps.api.agents.stage4_factcheck.common import nli_probs
        floor = float(os.getenv("STAGE5_ENTAIL_MIN", "").strip() or DEFAULT_SCOPE_ENTAIL_MIN)
        return float(nli_probs([(quote, claim_text)])[0]["entailment"]) >= floor
    except Exception:
        return False


# ----------------------------------------------------------------------------------------------------------------------- helpers
def _norm(text) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _as_list(value) -> list:
    if isinstance(value, str):
        try:
            import json
            value = json.loads(value)
        except ValueError:
            return []
    return value if isinstance(value, list) else []


def _float(value, default: Optional[float] = None) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def evidence_from_row(e: dict) -> Optional[Evidence]:
    """One Stage 4 evidence entry as an Evidence; None when it has no quote (an entry without its quote cannot back a sentence)."""
    quote = re.sub(r"\s+", " ", str(e.get("quote") or "")).strip()
    if not quote:
        return None
    sid = str(e.get("source_id") or "")
    title = str(e.get("source_title") or e.get("title") or "").strip()
    return Evidence(source_id=sid, title=title, quote=quote, relation=str(e.get("relation") or "supports"),
                    evidence_level=str(e.get("evidence_level") or "abstract"), ref_key=ref_key_of(title, sid),
                    reliability=_float(e.get("reliability")), prob=_float(e.get("prob")), via=e.get("via") or None,
                    near_claim=(str(e["near_claim"]).strip() or None) if e.get("near_claim") else None)


def _is_strong(ev: Evidence) -> bool:
    return ev.evidence_level == "full_text" or ev.via == STRONG_VIA


def primary_evidence(claim: Claim) -> Optional[Evidence]:
    """The supporting quote the claim stands on: the strongest supporting entry (full text / Stage 3 judge first), else the first one."""
    sup = claim.supporting()
    strong = [e for e in sup if _is_strong(e)]
    return (strong or sup or [None])[0]


def claim_from_row(sub_question_id: str, row: dict) -> Optional[Claim]:
    """One Stage 4 fact_claims row (dict) as a Claim with its tier (before the single-source filters); None for a row without claim text."""
    text = re.sub(r"\s+", " ", str(row.get("claim") or "")).strip()
    if not text:
        return None
    evidence = [ev for ev in (evidence_from_row(e) for e in _as_list(row.get("evidence")) if isinstance(e, dict)) if ev]
    evidence.sort(key=lambda e: {"supports": 0, "near_match": 1, "contradicts": 2}.get(e.relation, 3))     # stable: supports first
    label, contested = str(row.get("label") or ""), bool(row.get("contested"))
    claim = Claim(claim_id=make_claim_id(sub_question_id, text), sub_question_id=sub_question_id, text=text, label=label, tier=None,
                  contested=contested, confidence=_float(row.get("confidence"), 0.0) or 0.0, evidence=evidence)
    claim.support_docs = _int(row.get("support_doc_count"), len({e.ref_key for e in claim.supporting()}))
    claim.contra_docs = _int(row.get("contra_doc_count"), len({e.ref_key for e in claim.conflicting()}))
    claim.tier, claim.filtered_reason = _tier_of(claim)
    return claim


def _tier_of(claim: Claim) -> tuple:
    """(tier, filtered_reason) from the label and the evidence, before the single-source filters."""
    if claim.label == LABEL_CONTRADICTED or claim.contested:
        return TIER_DISPUTED, None
    tier = LABEL_TIER.get(claim.label)
    if tier is None:
        return None, FILTER_UNKNOWN
    supports = claim.supporting()
    if not supports:
        return None, FILTER_INCOMPLETE
    if tier == TIER_SUPPORTED and len({e.ref_key for e in supports}) < 2:
        return None, FILTER_INCOMPLETE                      # "Two sources report ..." must be true of the evidence we hold
    if tier == TIER_PARTLY and not any(e.relation == "near_match" for e in claim.evidence):
        return None, FILTER_INCOMPLETE                      # "[A] reports X; [B] makes a related point" needs both wordings
    return tier, None


def _rank_key(claim: Claim) -> tuple:
    """Best first: full text / confirmed by Stage 3, then the level of the evidence, then confidence; the text makes ties deterministic."""
    ev = primary_evidence(claim)
    level = LEVEL_RANK.get(ev.evidence_level, 0) if ev else 0
    return (-int(bool(ev and _is_strong(ev))), -level, -claim.confidence, claim.text.lower(), claim.claim_id)


# ----------------------------------------------------------------------------------------------------------------------- build_claims
def build_claims(sub_question_inputs: list, *, scope_check: Optional[Callable[[str, str], bool]] = None, per_source: Optional[int] = None,
                 per_section: Optional[int] = None, needs_strong: Optional[bool] = None, scope_on: Optional[bool] = None) -> list:
    """All claims of the run as Claim objects: tier assigned, single-source filters applied (a filtered claim has tier None and a filtered_reason).

    `sub_question_inputs` = loader's inputs["sub_questions"] (each has "id" and "claims": Stage 4 rows). The result is ordered by section, then
    tier, confidence, text, so it does not depend on the order of the database rows. Keyword arguments override the env switches (tests).
    `scope_check(claim_text, quote) -> bool` is only called when the scope check is on (default: Stage 4's NLI model)."""
    cap_source = max_per_source() if per_source is None else per_source
    cap_section = max_single_per_section() if per_section is None else per_section
    strong_needed = single_needs_strong() if needs_strong is None else needs_strong
    scope_on = scope_check_enabled() if scope_on is None else scope_on
    scope_check = (scope_check or default_scope_check) if scope_on else None

    sections: list[list] = []
    for sq in sub_question_inputs or []:
        sid = str(sq.get("id") or "")
        by_id: dict[str, Claim] = {}
        for row in sq.get("claims") or []:
            c = claim_from_row(sid, row) if isinstance(row, dict) else None
            if c and (c.claim_id not in by_id or _rank_key(c) < _rank_key(by_id[c.claim_id])):
                by_id[c.claim_id] = c                       # the same wording twice in one sub-question: keep the better row
        ordered = sorted(by_id.values(), key=lambda c: (_tier_index(c), -c.confidence, c.text.lower(), c.claim_id))
        _drop_mirrors(ordered)
        sections.append(ordered)

    singles = [c for section in sections for c in section if c.tier == TIER_SINGLE]
    for c in list(singles):                                 # 1. strong evidence, 2. scope
        ev = primary_evidence(c)
        if strong_needed and not any(_is_strong(e) for e in c.supporting()):
            _drop(c, FILTER_WEAK)
        elif scope_check is not None and not _scope_ok(scope_check, c, ev):
            _drop(c, FILTER_SCOPE)
    kept = sorted([c for c in singles if c.tier == TIER_SINGLE], key=_rank_key)
    if cap_source >= 1:                                     # 3. per document, over the whole report
        used: dict[str, int] = {}
        for c in kept:
            key = (primary_evidence(c) or Evidence("", "", "")).ref_key
            used[key] = used.get(key, 0) + 1
            if used[key] > cap_source:
                _drop(c, FILTER_SOURCE_CAP)
    if cap_section >= 1:                                    # 4. per section, different documents first
        for section in sections:
            mine = sorted([c for c in section if c.tier == TIER_SINGLE], key=_rank_key)
            seen: dict[str, int] = {}
            order = []
            for c in mine:
                key = (primary_evidence(c) or Evidence("", "", "")).ref_key
                order.append((seen.get(key, 0), _rank_key(c), c))
                seen[key] = seen.get(key, 0) + 1
            order.sort(key=lambda t: (t[0], t[1]))
            for _, _, c in order[cap_section:]:
                _drop(c, FILTER_SECTION_CAP)
    return [c for section in sections for c in section]


def _norm_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _near_of(claim: Claim) -> str:
    for e in claim.evidence:
        if e.relation == "near_match" and e.near_claim:
            return _norm_text(e.near_claim)
    return ""


def _drop_mirrors(claims: list) -> None:
    """Stage 4 can label two claims "partly supported" that are each other's near-match (A's close variant is B, B's is A): reading both is the same
    finding twice. Keep the first, drop the later one (the claims are in rank order, so the better one stays)."""
    seen: set = set()
    for c in claims:
        if c.tier != TIER_PARTLY:
            continue
        mine, near = _norm_text(c.text), _near_of(c)
        if not near:
            continue
        if (near, mine) in seen:
            _drop(c, FILTER_MIRROR)
        else:
            seen.add((mine, near))


def _tier_index(claim: Claim) -> int:
    return TIERS.index(claim.tier) if claim.tier in TIERS else len(TIERS)


def _drop(claim: Claim, reason: str) -> None:
    claim.tier, claim.filtered_reason = None, reason


def _scope_ok(check: Callable[[str, str], bool], claim: Claim, ev: Optional[Evidence]) -> bool:
    try:
        return bool(ev) and bool(check(claim.text, ev.quote))
    except Exception:
        return False                                        # fail closed


def count_claims(claims: list) -> dict:
    """{"total", "supported", "partly", "single", "disputed", "filtered": {reason: n}, "filtered_total"} for the claims of a section or of the run."""
    out = {"total": len(claims), **{t: sum(1 for c in claims if c.tier == t) for t in TIERS}, "filtered": {}}
    for c in claims:
        if c.tier is None:
            out["filtered"][c.filtered_reason or FILTER_UNKNOWN] = out["filtered"].get(c.filtered_reason or FILTER_UNKNOWN, 0) + 1
    out["filtered_total"] = sum(out["filtered"].values())
    return out


# ----------------------------------------------------------------------------------------------------------------------- jobs
def make_jobs(section_id: str, claims: list, max_per_job: int = MAX_PER_JOB) -> list:
    """Sentence jobs of one section: claims of the same writable tier, at most `max_per_job` (3) each. Order: tier (supported, partly, single), then
    confidence (best first), so the sentences read strongest first. Job ids hash the section, the tier and the claim ids (stable across reruns)."""
    size_all = max(1, min(int(max_per_job or MAX_PER_JOB), MAX_PER_JOB))
    jobs = []
    for tier in WRITABLE_TIERS:
        size = min(size_all, PARTLY_PER_JOB) if tier == TIER_PARTLY else size_all
        mine = sorted([c for c in claims if c.tier == tier], key=lambda c: (-c.confidence, c.text.lower(), c.claim_id))
        for i in range(0, len(mine), size):
            group = mine[i:i + size]
            digest = hashlib.sha1(f"{section_id}|{tier}|{','.join(sorted(c.claim_id for c in group))}".encode("utf-8")).hexdigest()[:10]
            jobs.append(Job(job_id=f"j_{digest}", section_id=section_id, tier=tier, claims=group))
    return jobs


# ----------------------------------------------------------------------------------------------------------------------- disagreements
def _match_evidence(evidence: list, quote: str, title: str) -> Optional[Evidence]:
    """The evidence entry of a contradiction side: same quote (after whitespace/case normalising), else the same document."""
    q = _norm(quote)
    for e in evidence:
        if q and _norm(e.quote) == q:
            return e
    key = ref_key_of(title, "") if title else ""
    return next((e for e in evidence if key and e.ref_key == key), None)


def disputed_for_section(claims: list, contradictions: list) -> list:
    """The "Sources disagree" pairs of a section, as Disagreement objects. Two sources, both shown with their quotes:

    1. every row of the contradictions table (dicts with claim_a, claim_b, source_a_title, source_b_title, quote_a, quote_b, prob, reason). It is linked
       to a claim BY TEXT (claim_a == claim.text); its sides are matched to that claim's evidence (quote_a to a supporting entry, quote_b / the source
       title to an entry with relation "contradicts") to get the document keys. An unlinked row is kept (claim_id None).
    2. every disputed claim (contradicted, or contested) whose conflicting entries are not already covered by a row: its best supporting quote against
       each conflicting quote (claim_b is then the conflicting quote itself; the table has no wording for it).
    The order does not depend on the input order."""
    by_text: dict[str, Claim] = {}
    for c in claims:
        by_text.setdefault(_norm(c.text), c)
    out: list[Disagreement] = []
    covered: set = set()
    for row in contradictions or []:
        if not isinstance(row, dict):
            continue
        claim = by_text.get(_norm(row.get("claim_a")))
        title_a, title_b = str(row.get("source_a_title") or ""), str(row.get("source_b_title") or "")
        ev_a = _match_evidence(claim.supporting(), row.get("quote_a") or "", title_a) if claim else None
        if claim and ev_a is None and not (row.get("quote_a") or title_a):
            ev_a = (claim.supporting() or [None])[0]        # a row that names no side A: the detector's side A is the claim's first supporting quote
        ev_b = _match_evidence(claim.conflicting(), row.get("quote_b") or "", title_b) if claim else None
        key_a = ev_a.ref_key if ev_a else ref_key_of(title_a, "")
        key_b = ev_b.ref_key if ev_b else ref_key_of(title_b, "")
        out.append(Disagreement(sub_question_id=(claim.sub_question_id if claim else str(row.get("sub_question_id") or "")),
                                claim_a=str(row.get("claim_a") or ""), claim_b=str(row.get("claim_b") or ""),
                                source_a_title=title_a or (ev_a.title if ev_a else ""), source_b_title=title_b or (ev_b.title if ev_b else ""),
                                quote_a=str(row.get("quote_a") or "") or (ev_a.quote if ev_a else ""),
                                quote_b=str(row.get("quote_b") or "") or (ev_b.quote if ev_b else ""),
                                ref_key_a=key_a, ref_key_b=key_b, claim_id=claim.claim_id if claim else None,
                                prob=_float(row.get("prob")), reason=(str(row["reason"]) if row.get("reason") else None)))
        if claim:
            covered.add((claim.claim_id, key_b))
    for c in sorted([c for c in claims if c.tier == TIER_DISPUTED], key=lambda c: (c.text.lower(), c.claim_id)):
        support = (c.supporting() or [None])[0]
        for conflict in c.conflicting():
            if support is None or (c.claim_id, conflict.ref_key) in covered:
                continue
            out.append(Disagreement(sub_question_id=c.sub_question_id, claim_a=c.text, claim_b=conflict.quote, source_a_title=support.title,
                                    source_b_title=conflict.title, quote_a=support.quote, quote_b=conflict.quote, ref_key_a=support.ref_key,
                                    ref_key_b=conflict.ref_key, claim_id=c.claim_id, prob=conflict.prob, reason=None))
    out.sort(key=lambda d: (_norm(d.claim_a), d.ref_key_b, _norm(d.quote_b), _norm(d.claim_b)))
    return out
