"""The assembler of Stage 5: turns the loader's input dict into the written report (structured dict + Markdown). Python decides what may be said and
builds every number, citation and gap sentence; the language model only phrases one sentence per small cluster of claims (writer.py) and compresses
the already validated sentences into a summary and a conclusion (summary.py).

    result = build_report(inputs, llm=None, check=None, nli=None, judge=None, cache=None, progress=None, workers=None, deterministic=False)
    result = {"status", "report", "markdown", "stats", "warnings", "model", "template_version"}        # never raises

Steps (each reported through `progress(step, message, **data)`; `data["state"]` is "running" (default) or "completed"):
  sections    claims -> tiers (tiers.build_claims), jobs (tiers.make_jobs), "Sources disagree" pairs (tiers.disputed_for_section), gaps (templates)
  write       one sentence per job, all sections in parallel (writer.write_sections); a failed sentence becomes the deterministic fallback sentence
  validate    every sentence: claim ids exist, the tier matches the claims, no [n] in the text (a sentence that fails is dropped and a warning added)
  summary     executive summary and conclusion, written LAST from the validated sentences (summary.write_summary / write_conclusion)
  references  numbering by first citation in RENDER ORDER (summary, sections, conclusion) in one pass over the finished text, then the final checks
`progress("note", message, code=..., level=...)` is a note (fallback sentences, dropped sentences), not a step.

Policy (docs/STAGE5.md): the Stage 4 label never changes; the tier only decides the wording. Supported = "Two sources report ...", partly = one
document plus a related point in another, single = attributed to one document and never stated as fact, disputed = only in "Sources disagree".
Introduction, limitations and gaps are Python templates (no LLM). A text field never holds a [n]: the Markdown renderer adds the markers.

deterministic=True (scripts/stage5_on_stored_run.py --dry): no LLM and no model at all; every sentence is the deterministic fallback sentence and the
summary is the extractive template. It costs nothing and is for looking at the structure of a stored run.

Status: completed | completed_with_warnings (a fallback or dropped sentence, or a failed final check) | insufficient_evidence (nothing eligible to
write about: Stage 4 off or failed, no claims, all claims disputed or filtered; no LLM call) | failed (an internal error; the run is never failed by it).
"""
import logging
import re
import time
from datetime import datetime, timezone
from typing import Optional

from apps.api.agents.stage5_report import grounding, hedging, references, settings, summary, tiers, validators, writer
from apps.api.agents.stage5_report.schema import (ORIGIN_FALLBACK, ORIGIN_LLM, ORIGIN_TEMPLATE, STATUS_COMPLETED, STATUS_FAILED, STATUS_INSUFFICIENT,
                                                  STATUS_WARNINGS, TIER_DISPUTED, TIER_PARTLY, TIER_SINGLE, TIER_SUPPORTED, Job, Section, Sentence)

logger = logging.getLogger("apps.api.agents.stage5_report")

PER_SECTION_CANDIDATES = 3      # sentences of one section offered to the summary (supported first, then partly, then single)
MIN_CANDIDATES = 6              # a small report still offers the summary this many sentences when it has them
MAX_CANDIDATES = 12             # sentences offered to the summary / conclusion in all
MAX_LIST_ITEMS = 6              # texts of one kind (uncovered details ...) named in a gap sentence before "and N more"
MAX_REASON_CHARS = 300

STANDING_CAVEAT = ("The check for conflicts between sources compares only the most similar pairs of statements and is automatic, not reviewed by a "
                   "person: a disagreement outside those pairs is not reported, and a reported one may be a false alarm.")
LEGEND = ("How to read the findings: a sentence that starts with \"Two sources report\" is stated by two or more documents; a finding marked "
          "(partly supported) rests on one document with a related point in another; single-source findings are attributed to one document and are not "
          "confirmed. Citation numbers point to the references at the end.")
SINGLE_SHARE_SENTENCE = "These findings rest on one source each and are attributed to that source."
SINGLE_SHARE_CONCLUSION = "The evidence gathered is limited: each of these findings is attributed to one source."
TIER_LABEL_MD = {TIER_SINGLE: "*(one source, not confirmed)*", TIER_PARTLY: "*(partly supported)*"}
FILTER_TEXT = {
    tiers.FILTER_WEAK: "the only quote came from an abstract or a web snippet that Stage 3 had not confirmed",
    tiers.FILTER_SCOPE: "the claim said more than its quote",
    tiers.FILTER_SOURCE_CAP: "the document already had the maximum number of single-source claims in the report",
    tiers.FILTER_SECTION_CAP: "the section already had the maximum number of single-source claims",
    tiers.FILTER_INCOMPLETE: "the stored evidence did not match the claim's label",
    tiers.FILTER_UNKNOWN: "the claim had an unknown label",
    tiers.FILTER_MIRROR: "the same two statements were already reported the other way round",
}
_MARKER_RE = re.compile(r"\s*\[\s*\d+(?:\s*[,;\-–]\s*\d+)*\s*\]")
_STRENGTH = hedging.STRENGTH


# ----------------------------------------------------------------------------------------------------------------------- small helpers
def _emit(progress, step: str, message: str = "", **data) -> None:
    """A progress report never raises out of the assembler."""
    if progress is None:
        return
    try:
        progress(step, message, **data)
    except Exception:
        logger.debug("stage 5 progress callback failed", exc_info=True)


def _n(count: int, word: str, plural: Optional[str] = None) -> str:
    return f"{count} {word if count == 1 else (plural or word + 's')}"


def _scrub(text) -> str:
    """Whitespace collapsed and any [n] marker removed: the text fields of the report never hold a citation marker."""
    return " ".join(_MARKER_RE.sub("", str(text or "")).split())


def _cut(text, limit: int = MAX_REASON_CHARS) -> str:
    t = " ".join(str(text or "").split())
    return t if len(t) <= limit else t[:limit - 3].rstrip() + "..."


def _name_list(items: list, limit: int = MAX_LIST_ITEMS) -> str:
    shown = [_cut(i, 160) for i in items[:limit]]
    more = len(items) - len(shown)
    return "; ".join(shown) + (f"; and {more} more" if more > 0 else "")


def _end(text: str) -> str:
    """The text with a full stop, unless it already ends with one (or with ? or !)."""
    t = text.rstrip()
    return t if t[-1:] in (".", "?", "!") else t + "."


def _not_used(total: int, filtered: dict, verb: str = "not used") -> str:
    """'2 claims not used because X' (one reason) or '3 claims not used: 2 because X; 1 because Y' (several)."""
    items = sorted((filtered or {}).items(), key=lambda kv: (-kv[1], kv[0]))
    if len(items) == 1:
        return f"{_n(total, 'claim')} {verb} because {FILTER_TEXT.get(items[0][0], items[0][0])}"
    return f"{_n(total, 'claim')} {verb}: " + "; ".join(f"{n} because {FILTER_TEXT.get(reason, reason)}" for reason, n in items)


MAX_REASONS = 4


def _sentence_dict(s: Sentence, refs: list) -> dict:
    out = {"text": _scrub(s.text), "claimIds": list(s.claim_ids), "refs": list(refs), "tier": s.tier, "origin": s.origin}
    if s.origin != ORIGIN_TEMPLATE:         # the audit trail: how many model attempts, and why a sentence was rejected (at most MAX_REASONS short reasons)
        out["attempts"] = int(s.attempts or 0)
        reasons = [_cut(r, 200) for r in (s.reasons or []) if str(r).strip()][:MAX_REASONS]
        if reasons:
            out["reasons"] = reasons
    return out


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ----------------------------------------------------------------------------------------------------------------------- templates: gaps
def _section_gaps(sq: dict, counts: dict, wrote: int, fact_ran: bool) -> list:
    """The gap sentences of one section, all by template from Stage 3's coverage view, Stage 4's error and the filtered counts."""
    gaps: list = []
    cov = sq.get("coverage") if isinstance(sq.get("coverage"), dict) else {}
    if sq.get("fact_error"):
        gaps.append(f"Fact checking failed for this sub-question ({_cut(sq['fact_error'], 160)}), so none of its claims was checked.")
    elif fact_ran and not sq.get("claims"):
        gaps.append("No claims were checked for this sub-question, so no finding can be reported for it.")
    if not cov.get("present"):
        gaps.append("No coverage information from the evidence-collection stage is available for this sub-question.")
    else:
        if cov.get("uncovered_details"):
            gaps.append(_end("The collected evidence does not sufficiently answer: " + _name_list(cov["uncovered_details"])))
        if cov.get("uncovered_aspects"):
            gaps.append(_end("Aspects with no sufficient evidence: " + _name_list(cov["uncovered_aspects"])))
        if cov.get("known_gaps"):
            gaps.append(_end("Evidence not found, even after a second search, for: " + _name_list(cov["known_gaps"])))
        if cov.get("unjudged_aspects"):
            gaps.append(_end("Aspects that could not be judged: " + _name_list(cov["unjudged_aspects"])))
        if cov.get("covered_by_synthesis"):
            gaps.append(_end("Covered only by combining several sources, not by one source that states it: " + _name_list(cov["covered_by_synthesis"])))
        if cov.get("digest_failures"):
            gaps.append(f"{_n(int(cov['digest_failures']), 'source')} could not be summarised, so their findings are missing here.")
        if cov.get("fallback_reason"):
            gaps.append("The evidence-collection stage used a fallback: " + _cut(cov["fallback_reason"], 160) + ".")
    if counts.get("filtered_total"):
        gaps.append(_end(_not_used(counts["filtered_total"], counts.get("filtered") or {})))
    if counts.get("disputed"):
        gaps.append(f"{_n(counts['disputed'], 'claim')} in dispute between sources; see \"Sources disagree\".")
    if not wrote:
        gaps.append("No claim in this section met the conditions for being written about.")
    return gaps


# ----------------------------------------------------------------------------------------------------------------------- templates: introduction, limitations
def _documents_in(claims: list) -> int:
    return len({e.ref_key or e.source_id for c in claims for e in c.evidence if (e.ref_key or e.source_id)})


def _introduction(inputs: dict, sections: list, totals: dict, documents: int) -> list:
    question = _scrub(inputs.get("question"))
    out = []
    if question:
        out.append(f"This report addresses the research question: \"{question}\".")
    context = _scrub(inputs.get("domain_context"))
    if context:
        out.append("Context used to read the question: " + context.rstrip(".") + ".")
    if sections:
        titled = "; ".join(f"({i}) {s.title}" for i, s in enumerate(sections, 1))
        out.append(_end(f"The question was split into {_n(len(sections), 'sub-question')}, covered in this order: {titled}"))
    if totals["total"]:
        line = (f"The findings are based on {_n(documents, 'document')} and {_n(totals['total'], 'claim')} that were checked across sources: "
                f"{totals[TIER_SUPPORTED]} stated by two or more documents, {totals[TIER_PARTLY]} stated by one document with a related point in another, "
                f"{totals[TIER_SINGLE]} stated by a single document and {totals[TIER_DISPUTED]} in dispute between sources.")
        if totals["filtered_total"]:
            line += f" {_n(totals['filtered_total'], 'further claim')} were not used (see the limitations)."
        out.append(line)
    else:
        out.append("No checked claims were available for this question.")
    out.append("Every sentence is built from stored claims and their verbatim quotes, each citation number points to the document that holds the quote, "
               "and the checks behind it are automatic: none of the findings was reviewed by a person.")
    return out


def _limitations(inputs: dict, sections: list, totals: dict, body_stats: dict, warnings_fallback: int, dropped: int) -> list:
    hints = inputs.get("status_hints") if isinstance(inputs.get("status_hints"), dict) else {}
    out = []
    if inputs.get("fact_error"):
        out.append(f"Fact checking (Stage 4) failed for this run ({_cut(inputs['fact_error'], 200)}), so no claim could be classified.")
    elif not inputs.get("fact_ran") and not totals["total"]:
        out.append("Fact checking (Stage 4) produced no checked claims for this run (it was switched off, failed or found nothing), so there is nothing to write about.")
    if totals["total"]:
        out.append(f"Of {_n(totals['total'], 'checked claim')}: {totals[TIER_SUPPORTED]} stated by two or more documents, {totals[TIER_PARTLY]} by one document "
                   f"with a related point in another, {totals[TIER_SINGLE]} by a single document, and {totals[TIER_DISPUTED]} in dispute between sources. "
                   "Single-source findings are attributed to one document and are not confirmed by a second source.")
    written = body_stats.get("written", {})
    writable = sum(written.get(t, 0) for t in (TIER_SUPPORTED, TIER_PARTLY, TIER_SINGLE))
    if writable and written.get(TIER_SINGLE):
        share = round(100 * written[TIER_SINGLE] / writable)
        out.append(f"{share}% of the findings written here ({written[TIER_SINGLE]} of {writable}) rest on a single document.")
    if totals["filtered_total"]:
        out.append(_end(_not_used(totals["filtered_total"], totals["filtered"], "left out")))
    empty = [s.title for s in sections if not any(True for x in s.sentences)]
    if empty:
        out.append(_end("No eligible claim was found for: " + _name_list(empty)))
    if warnings_fallback:
        verb = "uses" if warnings_fallback == 1 else "use"
        out.append(f"{_n(warnings_fallback, 'sentence')} {verb} a fixed template wording (the claim's own wording, or a body sentence repeated) because the written sentence did not pass the automatic checks.")
    if dropped:
        out.append(f"{_n(dropped, 'sentence')} were left out because they failed a final check.")
    if hints.get("fact_failed_sub_questions"):
        out.append(f"Fact checking failed for {_n(len(hints['fact_failed_sub_questions']), 'sub-question')}; its claims are missing.")
    if hints.get("judge_failures"):
        out.append(f"The fact-checking judges failed {hints['judge_failures']} time(s): labels are cautious but may be incomplete.")
    if hints.get("sources_without_metadata"):
        out.append(f"{_n(int(hints['sources_without_metadata']), 'cited source')} had no stored bibliographic data, so their references show the title only.")
    out.append(STANDING_CAVEAT)
    return out


# ----------------------------------------------------------------------------------------------------------------------- sentence checks
def _tier_of_claims(claim_ids: list, claims_by_id: dict) -> Optional[str]:
    """The weakest tier among the claims of a sentence (None when one of the ids is unknown)."""
    found = [claims_by_id.get(i) for i in claim_ids]
    if not found or any(c is None for c in found):
        return None
    tiers_ = [c.tier for c in found]
    if any(t not in _STRENGTH for t in tiers_):
        return TIER_DISPUTED
    return min(tiers_, key=lambda t: _STRENGTH[t])


def _split_fallbacks(sentences: list, claims_by_id: dict, section_id: str) -> list:
    """A deterministic (fallback) sentence that joins 2-3 claims is hard to read and gives its citations to all of them: write one sentence per claim
    instead (same tier wording, same reasons). Sentences written by the LLM are not touched."""
    out = []
    for s in sentences:
        ids = [i for i in (s.claim_ids or []) if i in claims_by_id]
        if s.origin != ORIGIN_FALLBACK or len(ids) < 2 or len(ids) != len(s.claim_ids):
            out.append(s)
            continue
        for n, cid in enumerate(ids, 1):
            job = Job(job_id=f"{s.job_id}.{n}", section_id=section_id, tier=s.tier, claims=[claims_by_id[cid]])
            text = hedging.fallback_sentence(job)
            if text:
                out.append(Sentence(text=text, claim_ids=[cid], job_id=job.job_id, tier=s.tier, origin=ORIGIN_FALLBACK, attempts=s.attempts,
                                    reasons=list(s.reasons or [])))
    return out


def _body_problems(s: Sentence, claims_by_id: dict) -> list:
    """Why a body sentence may not enter the report (empty = fine): empty text, unknown claim ids, or a tier that is not the tier of its claims."""
    problems = []
    if not _scrub(s.text):
        problems.append("empty text")
    if not s.claim_ids:
        problems.append("no claim id")
    else:
        unknown = [i for i in s.claim_ids if i not in claims_by_id]
        if unknown:
            problems.append("unknown claim id " + ", ".join(unknown))
        else:
            weakest = _tier_of_claims(s.claim_ids, claims_by_id)
            if weakest != s.tier:
                problems.append(f"tier {s.tier} does not match the tier of its claims ({weakest})")
    return problems


# ----------------------------------------------------------------------------------------------------------------------- summary / conclusion
def _candidates(section_sentences: list, role: str = "summary") -> list:
    """The validated sentences offered to the summary or to the conclusion. The planner puts the question itself last ("background first, core last"),
    so the LAST section comes first: the summary gets its first sentences (the job order is supported, partly, single) and the first sentence of every
    other section; the conclusion gets the next sentences of the last section and the second sentence of every other section, so the two do not
    repeat each other. A report too small for that gives the conclusion the same candidates as the summary."""
    sections = [s for s in section_sentences if s]
    if not sections:
        return []
    last, others = sections[-1], sections[:-1]
    first = list(last[:PER_SECTION_CANDIDATES]) + [s[0] for s in others]
    reverse_order = [s for sec in reversed(sections) for s in sec]              # last section first: what is left over, in order of importance
    if len(first) < MIN_CANDIDATES:
        first += [s for s in reverse_order if s not in first][:MIN_CANDIDATES - len(first)]
    if role == "summary":
        return first
    rest = [s for s in reverse_order if s not in first]
    out = list(last[PER_SECTION_CANDIDATES:2 * PER_SECTION_CANDIDATES]) + [s[1] for s in others if len(s) > 1]
    out = [s for s in out if s not in first] or rest
    return out if len(out) >= 3 else first


def _conclusion_check(summary_sentences, body_sentences) -> list:
    """The conclusion may use summarising connectives ("overall"); everything else (numbers, names, hedge strength, length) is as strict as the summary."""
    return validators.check_summary(summary_sentences, body_sentences, min_sentences=3, max_sentences=4, allow_connectives=True)


def _limitation_sentence(text: str, body: list, kind: str, current: list) -> Optional[Sentence]:
    """One template sentence about the single-source share, added to the summary or conclusion only when the validators accept it (mapped to a
    single-tier body sentence, so it may not be stronger than that) and the length limit leaves room."""
    singles = [b["n"] for b in body if b["tier"] == TIER_SINGLE]
    high = 5 if kind == "summary" else 4
    if not singles or len(current) >= high or len(singles) * 2 <= len(body):
        return None
    try:
        reasons = validators.check_summary([{"text": text, "from_sentences": [singles[0]]}], body, min_sentences=1, max_sentences=5, allow_connectives=True)
    except Exception:
        return None
    if reasons:
        return None
    return Sentence(text=text, claim_ids=[], job_id=f"{kind}_limitation", tier=TIER_SINGLE, origin=ORIGIN_TEMPLATE, attempts=0)


# ----------------------------------------------------------------------------------------------------------------------- the build
def build_report(inputs: dict, *, llm=None, check=None, nli=None, judge=None, cache=None, progress=None, workers=None, deterministic: bool = False) -> dict:
    """The written report of one run (see the module docstring). Never raises: an internal error gives status "failed" with the error in `warnings`."""
    t0 = time.time()
    try:
        return _build(inputs if isinstance(inputs, dict) else {}, llm, check, nli, judge, cache, progress, workers, deterministic, t0)
    except Exception as e:                                  # noqa: BLE001  (a Stage 5 failure never fails the run)
        logger.exception("Stage 5 failed")
        return failed_result(inputs, e, seconds=time.time() - t0, deterministic=deterministic)


def failed_result(inputs, error, *, seconds: float = 0.0, deterministic: bool = False) -> dict:
    """The result for an internal error: status failed, a minimal report, the error text in the warnings."""
    question = _scrub(inputs.get("question")) if isinstance(inputs, dict) else ""
    message = f"The written report could not be produced: {type(error).__name__ if isinstance(error, BaseException) else 'error'}: {_cut(error, 200)}"
    report = {"status": STATUS_FAILED, "question": question, "generatedAt": _now(), "overview": {"summary": [], "counts": {}}, "introduction": [], "sections": [],
              "limitations": [message], "conclusion": [], "references": [], "stats": {"seconds": round(seconds, 2)}, "warnings": [message]}
    return {"status": STATUS_FAILED, "report": report, "markdown": render_markdown(report), "stats": report["stats"], "warnings": [message],
            "model": "deterministic" if deterministic else settings.model(), "template_version": settings.template_version()}


def _build(inputs: dict, llm, check, nli, judge, cache, progress, workers, deterministic: bool, t0: float) -> dict:
    grounding.reset_stats()
    warnings: list = []
    sqs = [sq for sq in (inputs.get("sub_questions") or []) if isinstance(sq, dict)]

    # ---- 1. sections: claims, tiers, jobs, disagreements, gaps
    _emit(progress, "sections", "Choosing what can be written", state="running", sections=len(sqs))
    scope_check = None
    if nli is not None and not deterministic:
        scope_check = lambda text, quote: float(nli([(quote, text)])[0]["entailment"]) >= 0.5      # noqa: E731
    claims = tiers.build_claims(sqs, scope_check=scope_check, scope_on=False if deterministic else None)
    claims_by_id = {c.claim_id: c for c in claims}
    by_sq: dict = {}
    for c in claims:
        by_sq.setdefault(c.sub_question_id, []).append(c)
    totals = tiers.count_claims(claims)
    sections, jobs_by_section = [], []
    for i, sq in enumerate(sqs, 1):
        sid = str(sq.get("id") or "")
        mine = by_sq.get(sid, [])
        sections.append(Section(section_id=f"s{i}", sub_question_id=sid, title=_scrub(sq.get("title")) or f"Sub-question {i}",
                                detail_questions=[_scrub(d) for d in (sq.get("detail_questions") or []) if _scrub(d)],
                                disagreements=tiers.disputed_for_section(mine, sq.get("contradictions") or []), counts=tiers.count_claims(mine)))
        jobs_by_section.append(tiers.make_jobs(sid, mine))
    total_jobs = sum(len(j) for j in jobs_by_section)
    writable = totals[TIER_SUPPORTED] + totals[TIER_PARTLY] + totals[TIER_SINGLE]
    _emit(progress, "sections", f"{len(sections)} sections, {writable} claims to write, {total_jobs} sentences", state="completed",
          sections=len(sections), claims=totals["total"], writable=writable, jobs=total_jobs, disputed=totals[TIER_DISPUTED])

    # ---- 2. write the sentences (no LLM when there is nothing to write, or in deterministic mode)
    write_stats = [writer.new_stats()]
    sentences_by_section: list = [[] for _ in sections]
    if total_jobs:
        _emit(progress, "write", f"Writing {total_jobs} sentences", state="running", jobs=total_jobs)
        if deterministic:
            for k, jobs in enumerate(jobs_by_section):
                sentences_by_section[k] = [hedging.make_fallback_sentence(j, ["deterministic mode: no language model was used"]) for j in jobs]
            write_stats[0]["jobs"] = total_jobs
            write_stats[0]["fallback"] = total_jobs
        else:
            items = [(sections[k].title, jobs) for k, jobs in enumerate(jobs_by_section) if jobs]
            index = [k for k, jobs in enumerate(jobs_by_section) if jobs]
            results = writer.write_sections(items, workers=workers, llm=llm, check=check or grounding.make_check(nli, judge), cache=cache,
                                            progress=lambda step, message="", **data: _emit(progress, step, message, **data))
            for k, (sentences, st) in zip(index, results):
                sentences_by_section[k] = list(sentences)
                write_stats.append(st)

    # ---- 3. validate every sentence; a failing one is dropped and a warning added
    _emit(progress, "validate", "Checking the sentences", state="running")
    dropped = 0
    for k, sentences in enumerate(sentences_by_section):
        kept = []
        for s in _split_fallbacks(sentences, claims_by_id, sections[k].section_id):
            problems = _body_problems(s, claims_by_id)
            if problems:
                dropped += 1
                warnings.append(f"A sentence of \"{sections[k].title}\" was dropped: {'; '.join(problems)}.")
            else:
                kept.append(s)
        sentences_by_section[k] = kept
    llm_n = sum(1 for ss in sentences_by_section for s in ss if s.origin == ORIGIN_LLM)
    fallback_n = sum(1 for ss in sentences_by_section for s in ss if s.origin == ORIGIN_FALLBACK)
    written = {t: sum(1 for ss in sentences_by_section for s in ss if s.tier == t) for t in (TIER_SUPPORTED, TIER_PARTLY, TIER_SINGLE)}
    if fallback_n:
        _emit(progress, "note", f"{fallback_n} sentences use the template wording", code="stage5_fallback", level="warn", count=fallback_n)
    if dropped:
        _emit(progress, "note", f"{dropped} sentences were dropped by the final check", code="stage5_dropped", level="warn", count=dropped)
    _emit(progress, "validate", f"{sum(written.values())} sentences kept", state="completed", kept=sum(written.values()), fallback=fallback_n, dropped=dropped)

    # ---- 4. the executive summary and the conclusion, written last from the validated sentences
    all_sentences = [s for ss in sentences_by_section for s in ss]
    candidates = _candidates(sentences_by_section, "summary")
    candidates_c = _candidates(sentences_by_section, "conclusion")
    body = summary.select_body(list({id(s): s for s in candidates + candidates_c}.values()), 2 * MAX_CANDIDATES)
    summary_s: list = []
    conclusion_s: list = []
    sum_stats, concl_stats = writer.new_stats(), writer.new_stats()
    if body:
        _emit(progress, "summary", "Writing the summary and the conclusion", state="running", sentences=len(body))
        if deterministic:
            summary_s = summary.extractive("summary", body, origin=ORIGIN_TEMPLATE)
            conclusion_s = []
        else:
            common = dict(llm=llm, cache=cache, progress=progress, limit=MAX_CANDIDATES)
            summary_s, sum_stats = summary.write_summary(candidates, check_summary=None, **common)
            conclusion_s, concl_stats = summary.write_conclusion(candidates_c, check_summary=_conclusion_check, **common)
        summary_s, conclusion_s = list(summary_s), list(conclusion_s)
        if summary_s and (limit_s := _limitation_sentence(SINGLE_SHARE_SENTENCE, body, "summary", summary_s)):
            summary_s.append(limit_s)
        if conclusion_s and (limit_c := _limitation_sentence(SINGLE_SHARE_CONCLUSION, body, "conclusion", conclusion_s)):
            conclusion_s.append(limit_c)
        if conclusion_s and {_scrub(s.text) for s in conclusion_s if s.claim_ids} <= {_scrub(s.text) for s in summary_s}:
            conclusion_s = []                               # nothing to add to the summary (a tiny report): no second copy of it
        _emit(progress, "summary", f"{len(summary_s)} summary and {len(conclusion_s)} conclusion sentences", state="completed",
              summary=len(summary_s), conclusion=len(conclusion_s))
    summary_fallback = any(s.origin == ORIGIN_FALLBACK for s in summary_s)
    conclusion_fallback = any(s.origin == ORIGIN_FALLBACK for s in conclusion_s)
    top_fallback_n = sum(1 for s in summary_s + conclusion_s if s.origin == ORIGIN_FALLBACK)      # summary / conclusion sentences copied from the body
    if summary_fallback:
        warnings.append("The executive summary could not be written by the model within the checks; it repeats the strongest findings word for word.")
    if conclusion_fallback:
        warnings.append("The conclusion could not be written by the model within the checks; it repeats the strongest findings word for word.")

    # ---- 5. references: numbered by first citation in render order, in one pass over the finished text
    _emit(progress, "references", "Numbering the references", state="running")
    book = references.ReferenceBook(inputs.get("sources") or {}, accessed=references.accessed_date(inputs.get("created_at")))

    def refs_of(s: Sentence) -> list:
        found = [claims_by_id[i] for i in s.claim_ids if i in claims_by_id]
        if s.tier == TIER_SINGLE:
            # "One study reports ..." cites the one document its claim stands on (the strongest supporting quote), not a near match or a weaker second snippet
            return book.cite([e for e in (tiers.primary_evidence(c) for c in found) if e is not None])
        return book.cite(found)

    summary_d = [_sentence_dict(s, refs_of(s)) for s in summary_s]
    section_dicts = []
    for sec, sentences, sq in zip(sections, sentences_by_section, sqs):
        sentence_d = [_sentence_dict(s, refs_of(s)) for s in sentences]
        disagreement_d = [_disagreement_dict(d, book) for d in sec.disagreements]
        gaps = _section_gaps(sq, sec.counts, len(sentences), bool(inputs.get("fact_ran")))
        section_dicts.append({"id": sec.section_id, "title": sec.title, "subQuestionId": sec.sub_question_id, "detailQuestions": sec.detail_questions,
                              "sentences": sentence_d, "disagreements": disagreement_d, "gaps": gaps, "counts": _public_counts(sec.counts)})
    conclusion_d = [_sentence_dict(s, refs_of(s)) for s in conclusion_s]
    reference_d = [_reference_dict(r, book) for r in book.references()]

    # ---- 6. status, limitations, introduction, final checks
    stats_written = {"written": written}
    body_sentence_count = sum(written.values())
    if not writable or not body_sentence_count:
        status = STATUS_INSUFFICIENT
    else:
        status = STATUS_COMPLETED
    sections_for_text = sections
    for sec, sentences in zip(sections_for_text, sentences_by_section):
        sec.sentences = sentences
    documents = _documents_in(claims)
    report = {
        "status": status, "question": _scrub(inputs.get("question")), "generatedAt": _now(),
        "overview": {"summary": summary_d, "counts": {"sections": len(sections), "documents": documents, "claims": totals["total"],
                                                    "supported": totals[TIER_SUPPORTED], "partly": totals[TIER_PARTLY], "single": totals[TIER_SINGLE],
                                                    "disputed": totals[TIER_DISPUTED], "filtered": totals["filtered_total"], "sentences": body_sentence_count,
                                                    "disagreements": sum(len(s["disagreements"]) for s in section_dicts), "references": len(reference_d)}},
        "introduction": _introduction(inputs, sections, totals, documents),
        "sections": section_dicts,
        "limitations": _limitations(inputs, sections, totals, stats_written, fallback_n + top_fallback_n, dropped),
        "conclusion": conclusion_d, "references": reference_d,
    }
    warnings += final_checks(report, claims_by_id, body, summary_s, conclusion_s)
    if deterministic:
        warnings.append("Deterministic mode: no language model was used; every sentence is the template wording.")
    if status != STATUS_INSUFFICIENT and (warnings or fallback_n or dropped or summary_fallback or conclusion_fallback):
        status = STATUS_WARNINGS
    report["status"] = status
    report["warnings"] = warnings
    agg = writer.merge_stats(*write_stats, sum_stats, concl_stats)
    g = grounding.stats()
    stats = {
        "claims": {"total": totals["total"], "supported": totals[TIER_SUPPORTED], "partly": totals[TIER_PARTLY], "single": totals[TIER_SINGLE],
                   "disputed": totals[TIER_DISPUTED], "filtered": totals["filtered_total"]},
        "filtered": dict(totals["filtered"]), "written": written,
        "sentences": {"llm": llm_n, "fallback": fallback_n, "summary_conclusion_fallback": top_fallback_n, "dropped": dropped, "template": sum(1 for s in summary_s + conclusion_s if s.origin == ORIGIN_TEMPLATE)},
        "summary_fallback": summary_fallback, "conclusion_fallback": conclusion_fallback,
        "calls": agg["calls"], "prompt_tokens": agg["prompt_tokens"], "completion_tokens": agg["completion_tokens"], "tokens": agg["total_tokens"],
        "retried": agg["retried"], "cache_hits": agg["cache_hits"], "llm_errors": agg["llm_errors"], "rate_waits": agg["rate_waits"],
        "nli": {"calls": g.get("calls", 0), "pairs": g.get("nli_pairs", 0), "accepted": g.get("accepted_nli", 0), "contradiction_rejects": g.get("contradiction_rejects", 0),
                "errors": g.get("nli_errors", 0)},
        "judge": {"calls": g.get("judge_calls", 0), "accepted": g.get("accepted_judge", 0), "errors": g.get("judge_errors", 0)},
        "grounding_rejected": g.get("rejected", 0), "sections": len(sections), "references": len(reference_d), "seconds": round(time.time() - t0, 2),
    }
    report["stats"] = stats
    _emit(progress, "references", f"{len(reference_d)} references", state="completed", references=len(reference_d))
    return {"status": status, "report": report, "markdown": render_markdown(report), "stats": stats, "warnings": warnings,
            "model": "deterministic" if deterministic else settings.model(), "template_version": settings.template_version()}


def _public_counts(counts: dict) -> dict:
    return {"total": counts.get("total", 0), "supported": counts.get(TIER_SUPPORTED, 0), "partly": counts.get(TIER_PARTLY, 0), "single": counts.get(TIER_SINGLE, 0),
            "disputed": counts.get(TIER_DISPUTED, 0), "filtered": counts.get("filtered_total", 0)}


def _disagreement_dict(d, book) -> dict:
    """A "Sources disagree" pair for the report: both sides with their quote and the number of their reference (the other side is cited here too)."""
    ref_a = book.cite_key(d.ref_key_a, title=d.source_a_title) if d.ref_key_a else None
    ref_b = book.cite_key(d.ref_key_b, title=d.source_b_title) if d.ref_key_b else None
    note = "These sources disagree. The conflict check is automatic and was not reviewed by a person."
    if d.reason:
        note += " It noted: " + _cut(d.reason)
    return {"claimA": _scrub(d.claim_a), "claimB": _scrub(d.claim_b), "claimId": d.claim_id,
            "sideA": {"quote": _scrub(d.quote_a), "ref": ref_a, "title": _scrub(d.source_a_title)},
            "sideB": {"quote": _scrub(d.quote_b), "ref": ref_b, "title": _scrub(d.source_b_title)}, "note": note}


def _reference_dict(ref, book) -> dict:
    return {"number": ref.number, "title": ref.title, "authors": list(ref.authors or []), "year": ref.year, "venue": ref.venue, "doi": ref.doi, "url": ref.url,
            "kind": ref.kind, "evidenceLevel": ref.evidence_level, "sourceIds": list(ref.source_ids or []),
            "text": book.format_reference(ref), "markdown": book.format_reference(ref, markdown=True)}


# ----------------------------------------------------------------------------------------------------------------------- final checks (L4)
def final_checks(report: dict, claims_by_id: dict, body: list, summary_s: list, conclusion_s: list) -> list:
    """Warnings from the checks over the finished report: claim ids exist, ref numbers exist, a section with no text has a gap message, no [n] in a
    text field, the tier of a sentence is not stronger than its claims, and the summary / conclusion only use numbers and names of the body sentences.
    A failure is a warning (status completed_with_warnings), never a crash."""
    warnings: list = []
    numbers = {r["number"] for r in report.get("references", [])}
    sentence_groups = [("summary", report["overview"]["summary"]), ("conclusion", report.get("conclusion", []))] + \
                      [(f"section \"{s['title']}\"", s["sentences"]) for s in report.get("sections", [])]
    for where, group in sentence_groups:
        for s in group:
            if _MARKER_RE.search(s["text"]):
                warnings.append(f"A sentence of the {where} contains a citation marker in its text.")
            unknown = [i for i in s["claimIds"] if i not in claims_by_id]
            if unknown:
                warnings.append(f"A sentence of the {where} cites unknown claim id(s): {', '.join(unknown)}.")
            missing = [n for n in s["refs"] if n not in numbers]
            if missing:
                warnings.append(f"A sentence of the {where} cites reference number(s) that do not exist: {missing}.")
            if s["claimIds"] and not s["refs"]:
                warnings.append(f"A sentence of the {where} has claims but no reference.")
            weakest = _tier_of_claims(s["claimIds"], claims_by_id) if s["claimIds"] and not unknown else None
            if weakest and _STRENGTH.get(s["tier"], 0) > _STRENGTH.get(weakest, 0):
                warnings.append(f"A sentence of the {where} is worded as {s['tier']} but its claims are {weakest}.")
    for sec in report.get("sections", []):
        if not sec["sentences"] and not sec["disagreements"] and not sec["gaps"]:
            warnings.append(f"Section \"{sec['title']}\" has no text and no gap message.")
        for d in sec["disagreements"]:
            for side in ("sideA", "sideB"):
                ref = d[side]["ref"]
                if ref is not None and ref not in numbers:
                    warnings.append(f"A disagreement of section \"{sec['title']}\" cites reference {ref} that does not exist.")
    warnings += _summary_problems("summary", summary_s, body, lambda s, b: validators.check_summary(s, b, min_sentences=3, max_sentences=5))
    warnings += _summary_problems("conclusion", conclusion_s, body, _conclusion_check)
    return warnings


def _summary_problems(kind: str, sentences: list, body: list, check) -> list:
    """The summary / conclusion sentences that the model wrote are checked again against the body sentences they come from (numbers, names, hedge);
    template and extractive sentences must be word-for-word copies of a body sentence."""
    out = []
    body_text = {_scrub(b["text"]) for b in body}
    written = []
    for s in sentences:
        if not s.claim_ids:
            continue                                        # the template limitation sentence has no source sentences; it was validated when it was added
        if s.origin == ORIGIN_LLM:
            ids = set(s.claim_ids)
            written.append({"text": s.text, "from_sentences": [b["n"] for b in body if set(b["claim_ids"]) <= ids]})
        elif _scrub(s.text) not in body_text:
            out.append(f"A {kind} sentence from the extractive template is not a copy of a body sentence.")
    if written:
        try:
            for reason in check(written, body)[:4]:
                out.append(f"{kind}: {reason}")
        except Exception as e:                              # noqa: BLE001
            out.append(f"The {kind} check could not run ({type(e).__name__}).")
    return out


# ----------------------------------------------------------------------------------------------------------------------- Markdown
def _with_marker(text: str, refs: list) -> str:
    """The sentence with its [n] marker before the final full stop: 'Two sources report that X [1, 3].'"""
    t = (text or "").rstrip()
    marker = references.render_marker(refs)
    if not marker:
        return t
    if t and t[-1] in ".!?":
        return f"{t[:-1]} {marker}{t[-1]}"
    return f"{t} {marker}"


def _md_sentence(s: dict) -> str:
    label = TIER_LABEL_MD.get(s.get("tier"))
    return _with_marker(s["text"], s.get("refs") or []) + (f" {label}" if label else "")


def _md_side(side: dict) -> str:
    ref = f" [{side['ref']}]" if side.get("ref") is not None else ""
    title = f"{side['title']}{ref}: " if side.get("title") else (f"{ref.strip()}: " if ref else "")
    return f"{title}\"{side.get('quote', '')}\""


def render_markdown(report: dict) -> str:
    """The Markdown of a report dict (the structured report is the source of truth: this works from the stored JSON alone). Headings follow the planned
    structure: overview and executive summary, introduction, topic-wise findings (with "Sources disagree" and the gaps), limitations, conclusion, references."""
    r = report or {}
    lines = [f"# {r.get('question') or 'Research report'}", ""]
    overview = r.get("overview") or {}
    lines += ["## Research Overview and Executive Summary", "", f"> {LEGEND}", ""]
    counts = overview.get("counts") or {}
    if counts:
        lines += [f"Status: {r.get('status', '')}. {counts.get('sections', 0)} sections, {counts.get('documents', 0)} documents, {counts.get('claims', 0)} checked claims "
                  f"({counts.get('supported', 0)} stated by two or more documents, {counts.get('partly', 0)} partly supported, {counts.get('single', 0)} single-source, "
                  f"{counts.get('disputed', 0)} in dispute).", ""]
    if overview.get("summary"):
        lines += [" ".join(_md_sentence(s) for s in overview["summary"]), ""]
    else:
        lines += ["_No executive summary could be written: no finding met the conditions for being written about. See the limitations below._", ""]
    lines += ["## Introduction", ""]
    for p in r.get("introduction") or []:
        lines += [p, ""]
    lines += ["## Topic-wise Research Findings", ""]
    for i, sec in enumerate(r.get("sections") or [], 1):
        lines += [f"### {i}. {sec['title']}", ""]
        if sec.get("detailQuestions"):
            lines += ["*Detail questions:*"] + [f"- {d}" for d in sec["detailQuestions"]] + [""]
        for s in sec.get("sentences") or []:
            lines += [_md_sentence(s), ""]
        if sec.get("disagreements"):
            lines += ["#### Sources disagree", ""]
            for d in sec["disagreements"]:
                lines += [f"- **Sources disagree on:** {d['claimA']}", f"  - {_md_side(d['sideA'])}", f"  - {_md_side(d['sideB'])}", f"  - {d['note']}"]
            lines += [""]
        if sec.get("gaps"):
            lines += ["#### Evidence gaps", ""] + [f"- {g}" for g in sec["gaps"]] + [""]
    lines += ["## Limitations and Evidence Gaps", ""] + [f"- {x}" for x in r.get("limitations") or []] + [""]
    lines += ["## Conclusion", ""]
    if r.get("conclusion"):
        lines += [" ".join(_md_sentence(s) for s in r["conclusion"]), ""]
    else:
        lines += ["_The evidence gathered is too thin for a separate conclusion; see the executive summary and the limitations._", ""]
    lines += ["## References", ""]
    for ref in r.get("references") or []:
        lines += [f"[{ref['number']}] {ref.get('markdown') or ref.get('text') or ref.get('title')}", ""]
    if not r.get("references"):
        lines += ["_No references: no sentence of this report cites a source._", ""]
    if r.get("warnings"):
        lines += ["## Warnings", ""] + [f"- {w}" for w in r["warnings"]] + [""]
    return "\n".join(lines).rstrip() + "\n"
