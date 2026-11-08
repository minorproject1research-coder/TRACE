import logging
import os
import re
import json
import threading
from concurrent.futures import ThreadPoolExecutor

from apps.api import config
from apps.api.graph.state import SharedResearchState
import time

from apps.api.agents.stage3_summarizer import (
    chunk_selector,
    loop2,
    digest_generator,
    coverage_check,
    detail_aspects,
    evidence_judge,
)
from apps.api.services import db_service, groq_pool, llm_service, progress

logger = logging.getLogger("apps.api.agents.stage3_summarizer")

# keep small for the first run (free-tier API limits); raise to 8 and 5 later
MAX_PAPERS = int(os.getenv("MAX_PAPERS") or 3)
MAX_WEB = int(os.getenv("MAX_WEB_SEARCHES") or 2)


def _clean_topic(main_topic: str) -> str:
    """Strip leading 'What is' and trailing '?' from main topic."""
    t = main_topic.strip()
    t = re.sub(r"^what\s+is\s+", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\?$", "", t).strip()
    return t


def _workers() -> int:
    """Digest calls in flight at once. Default: one per Groq key. Groq limits are per ORGANIZATION, so extra workers on
    keys of the same account only trigger more 429s; set STAGE3_WORKERS to override."""
    configured = os.getenv("STAGE3_WORKERS", "").strip()
    if configured:
        return max(1, int(configured))
    return max(1, groq_pool.key_count()) if llm_service.BACKEND == "groq" else 1


def _prep_workers() -> int:
    """Sub-questions prepared at the same time (aspect split = a Groq call, chunking, embeddings). STAGE3_PREP_WORKERS, default 4; 1 = one by one."""
    try:
        return max(1, int(os.getenv("STAGE3_PREP_WORKERS", "").strip() or 4))
    except ValueError:
        return 4


def _overlap_enabled(qid: str | None = None) -> bool:
    """STAGE4_OVERLAP (default true) with FACTCHECK=true: Stage 4 of a sub-question starts as soon as Stage 3 has stored it. Only for a run of
    the graph (the planner announced it with factcheck_node.expect): a direct call of summarizer_node by a dev script has no Stage 4 node
    that would collect the jobs, and must not start any."""
    if not (config.factcheck_enabled() and os.getenv("STAGE4_OVERLAP", "true").strip().lower() not in ("0", "false", "no", "off")):
        return False
    if qid is None:
        return True
    from apps.api.graph.nodes import factcheck_node
    return factcheck_node.is_expected(qid)


_row = digest_generator.digest_row


class _Loop2Services(loop2.Services):
    """The real services, with progress reports for the run's event stream."""
    def __init__(self, query_id):
        super().__init__()
        self.query_id = query_id

    def progress(self, message, **data):
        progress.report(self.query_id, "summarizer", "loop2", "running", message, **data)


def _run_loop2(qid, state, sq, si, aspects, aspect_to_detail, details_for_coverage, digest_aspects, rows, chunk_lookup, jobs, candidates,
               judge_verdicts, cov, topic_aspect_used, deadline, digest_failures=0):
    """Loop 2 for one sub-question; returns the final coverage (rows and chunk_lookup are extended in place). Never raises."""
    n_rows = len(rows)
    try:
        svc = _Loop2Services(qid)
        papers = [j[2] for j in jobs if j[0] == si and j[1] == "paper"]
        ctx = loop2.SubQuestionContext(
            query_id=qid, sq=sq, aspects=aspects, aspect_to_detail=aspect_to_detail, details_for_coverage=details_for_coverage,
            digest_aspects=digest_aspects, rows=rows, chunk_lookup=chunk_lookup, papers=papers,
            topic_aspect_idx=len(aspects) - 1 if topic_aspect_used else None, digest_failures=digest_failures,
            anchor=state.task_plan.domain_anchor, context=state.task_plan.domain_context,
            tried_queries=list(sq.queries or []))
        pool = svc.pool_rows(qid, sq.id)
        ctx.paper_keys = {svc.paper_key(r) for r in pool}
        ctx.web_urls = {w.get("url") for w in db_service.get_web_sources_for_stage3(sq.id)}
        cov, _, _, info = loop2.run_subquestion(ctx, cov, candidates, judge_verdicts, svc, deadline)
        cov.setdefault("judge_stats", {})["loop2"] = info
        progress.report(qid, "summarizer", "loop2", "running", f"Loop 2 done for sub-question {si + 1}", subQuestion=sq.main_topic[:90],
                        searched=info["searched"], covered=info["covered"])
    except Exception:
        logger.exception("Loop 2 failed for sub-question '%s'; keeping the Stage 3 result", sq.main_topic[:50])
        del rows[n_rows:]                       # the coverage is the old one, so the digests must be the old ones too
    return cov


def _prepare_subquestion(qid, si, sq):
    """Step 1 for ONE sub-question: the aspects (a Groq call per detail question, cached) and the digest jobs with their selected chunks
    (chunking + embeddings). Independent of the other sub-questions, so they can run side by side. Returns (aspects, jobs of this sub-question)."""
    jobs = []
    cleaned_topic = _clean_topic(sq.main_topic)
    original_details = sq.detail_questions

    # Split details into aspects
    aspects, aspect_to_detail = detail_aspects.flatten_aspects(
        original_details, sq.id, cleaned_topic
    )
    aspects, aspect_to_detail, original_details = detail_aspects.with_topic_aspect(
        aspects, aspect_to_detail, original_details, sq.main_topic)     # the sub-question itself is judged too (TOPIC_ASPECT)
    logger.info(
        "Sub-question '%s': %d original details -> %d aspects",
        sq.main_topic[:50], len(original_details), len(aspects)
    )

    for p in db_service.get_papers_for_stage3(qid, sq.id)[:MAX_PAPERS]:
        selected = chunk_selector.select_chunks(
            sq.main_topic,
            chunk_selector.build_chunks(p),
            detail_questions=aspects,
            main_topic=cleaned_topic,
        )
        level = "full_text" if p.get("has_full_text") else "abstract"
        jobs.append((si, "paper", p, selected, p.get("combined_score"), level, aspects, original_details, aspect_to_detail))
    for w in db_service.get_web_sources_for_stage3(sq.id)[:MAX_WEB]:
        snippet = w.get("snippet") or ""
        if len(snippet) < 200:
            continue
        jobs.append((si, "web", w, [(0, snippet)], w.get("reliability_score"), "web_snippet", aspects, original_details, aspect_to_detail))
    return list(aspects), jobs


def _store_subquestion(qid, sq, si, total, rows, cov_row):
    """STAGE4_OVERLAP: store the digests and the coverage of ONE finished sub-question now (the rows of the other sub-questions are not
    touched: the tables are append-only and Stage 4 reads the newest rows of each sub-question), then queue its Stage 4 check on the
    background worker. A failed write raises as it did at the end of the node; a failure to START Stage 4 never does (factcheck_node
    checks a sub-question that was not started)."""
    db_service.write_digests(rows)
    db_service.write_coverage([cov_row])
    try:
        from apps.api.graph.nodes import factcheck_node
        if factcheck_node.start_in_background(qid, sq, si + 1, total):
            logger.info("Stage 4 queued for sub-question '%s' while Stage 3 goes on", sq.main_topic[:50])
    except Exception:
        logger.exception("Stage 4 could not be queued early for sub-question '%s'; it will be checked after Stage 3", sq.main_topic[:50])


def summarizer_node(state: SharedResearchState) -> dict:
    qid = state.task_plan.query_id
    try:
        return _summarize(state)
    except BaseException:
        if _overlap_enabled(qid):                   # Stage 3 failed: the Stage 4 jobs that were queued early are not wanted
            try:
                from apps.api.graph.nodes import factcheck_node
                factcheck_node.discard(qid)
            except Exception:
                logger.exception("could not cancel the early Stage 4 jobs")
        raise


def _summarize(state: SharedResearchState) -> dict:
    qid = state.task_plan.query_id
    sub_questions = state.task_plan.sub_questions
    progress.report(qid, "summarizer", "prepare", "running", "Selecting the passages to read (chunking, embeddings)", subQuestions=len(sub_questions))
    qid = state.task_plan.query_id
    overlap = _overlap_enabled(qid)
    if overlap:
        try:
            from apps.api.graph.nodes import factcheck_node
            factcheck_node.discard(qid, keep_expected=True)     # nothing left over from an earlier run of this query
        except Exception:
            logger.exception("Stage 4 overlap is not available; Stage 4 will run after Stage 3")
            overlap = False

    # 1. Prepare every digest job locally (chunking and embedding are fast); no model call yet. The sub-questions are independent, so
    #    they are prepared in a small thread pool; pool.map keeps their order, so the jobs list is the same as in a plain loop.
    jobs = []           # (sub_question index, source_type, source, selected chunks, weight, evidence level)
    digest_aspects_by_sq = {}       # what the first digest prompt saw, per sub-question (Loop 2 needs it)
    prep_workers = min(_prep_workers(), len(sub_questions))
    if prep_workers > 1:
        with ThreadPoolExecutor(max_workers=prep_workers, thread_name_prefix="stage3-prep") as prep_pool:
            prepared = list(prep_pool.map(lambda item: _prepare_subquestion(qid, item[0], item[1]), enumerate(sub_questions)))
    else:
        prepared = [_prepare_subquestion(qid, si, sq) for si, sq in enumerate(sub_questions)]
    for si, (sq_aspects, sq_jobs) in enumerate(prepared):
        digest_aspects_by_sq[si] = sq_aspects
        jobs.extend(sq_jobs)

    progress.report(qid, "summarizer", "prepare", "completed", f"{len(jobs)} sources to read", jobs=len(jobs),
                    papers=sum(1 for j in jobs if j[1] == "paper"), web=sum(1 for j in jobs if j[1] == "web"))

    # 2. Run the digests in parallel (Groq calls; the pool spreads them over the keys and waits out 429s).
    def run(job):
        si, _, src, selected, _, _, aspects, original_details, aspect_to_detail = job
        if not selected:
            return [], 0
        return digest_generator.generate_digest_with_retry(
            sub_questions[si].main_topic, selected, detail_aspects=aspects, main_topic=_clean_topic(sub_questions[si].main_topic),
            cache_scope=(str(sub_questions[si].id), str(src["id"])))

    workers = _workers()
    logger.info("Stage 3: %d digests for %d sub-questions, %d worker(s), %d Groq key(s)",
                len(jobs), len(sub_questions), workers, groq_pool.key_count() if llm_service.BACKEND == "groq" else 0)
    progress.report(qid, "summarizer", "digest", "running", f"Reading {len(jobs)} sources with the LLM", done=0, total=len(jobs), failures=0)
    counter, counter_lock = {"done": 0, "failures": 0}, threading.Lock()

    def tracked(job):
        result = run(job)
        with counter_lock:
            counter["done"] += 1
            counter["failures"] += 1 if result[1] else 0
            done, failures = counter["done"], counter["failures"]
            # reported inside the lock so the events arrive in counting order (a quick call: it only appends to the run's event list)
            progress.report(qid, "summarizer", "digest", "running", f"Read {done} of {len(jobs)} sources", done=done, total=len(jobs), failures=failures)
        return result

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(tracked, jobs))
    progress.report(qid, "summarizer", "digest", "completed", f"Read {len(jobs)} sources", done=len(jobs), total=len(jobs), failures=counter["failures"])
    findings_per_job = [r[0] for r in results]
    digest_failures_per_job = [r[1] for r in results]

    # 3. Assemble rows and coverage per sub-question, in the original order.
    all_rows, cov_rows, coverage = [], [], {}
    loop2_deadline = time.monotonic() + loop2.time_budget()
    for si, sq in enumerate(sub_questions):
        progress.report(qid, "summarizer", "judge", "running", f"Judging the evidence for sub-question {si + 1} of {len(sub_questions)}",
                        done=si, total=len(sub_questions), subQuestion=sq.main_topic[:90])
        rows = [_row(qid, sq.id, st, src, findings, weight, level)
                for (j_si, st, src, _, weight, level, _, _, _), findings in zip(jobs, findings_per_job) if j_si == si]
        
        # Get aspects and mapping for this sub-question
        cleaned_topic = _clean_topic(sq.main_topic)
        aspects, aspect_to_detail = detail_aspects.flatten_aspects(
            sq.detail_questions, sq.id, cleaned_topic
        )
        n_before = len(aspects)
        aspects, aspect_to_detail, details_for_coverage = detail_aspects.with_topic_aspect(
            aspects, aspect_to_detail, sq.detail_questions, sq.main_topic,
            enabled=detail_aspects.topic_aspect_for_judge())     # TOPIC_ASPECT=all: same aspects as in step 1; =judge: one more than in step 1
        topic_aspect_used = len(aspects) > n_before
        
        # Build chunk_lookup for judge context
        chunk_lookup = {}
        for (j_si, st, src, selected, weight, level, _, _, _), findings in zip(jobs, findings_per_job):
            if j_si != si:
                continue
            for chunk_id, chunk_text in selected:
                chunk_lookup[f"{src['id']}:{chunk_id}"] = chunk_text      # chunk ids repeat in every source: key by source too
        
        # Run judge for this sub-question if there are verified findings
        judge_verdicts = {}
        candidates = []
        has_verified = any(f.get("verified") for r in rows for f in r.get("findings", []))
        if has_verified and aspects:
            candidates, judge_verdicts = evidence_judge.run_judge_for_subquestion(
                aspects, rows, chunk_lookup, topic_aspect_idx=len(aspects) - 1 if topic_aspect_used else None
            )
        
        # Judge-based coverage with fallback
        cov = coverage_check.check_coverage_judged(
            aspects, aspect_to_detail, details_for_coverage, rows, judge_verdicts, candidates=candidates
        )
        sq_failures = sum(digest_failures_per_job[i] for i, (j_si, _, _, _, _, _, _, _, _) in enumerate(jobs) if j_si == si)
        if loop2.enabled() and has_verified and cov.get("uncovered_aspects"):
            cov = _run_loop2(qid, state, sq, si, aspects, aspect_to_detail, details_for_coverage, digest_aspects_by_sq.get(si, aspects), rows,
                             chunk_lookup, jobs, candidates, judge_verdicts, cov, topic_aspect_used, loop2_deadline, sq_failures)
        if isinstance(cov.get("judge_stats"), dict):
            cov["judge_stats"]["aspect_merge"] = detail_aspects.merge_mode()      # tools that rebuild this run's aspects need to know
            cov["judge_stats"]["topic_aspect"] = topic_aspect_used                # ... both markers
        # Add digest failures count
        cov["digest_failures"] = sq_failures
        
        coverage[sq.id] = cov
        progress.report(qid, "summarizer", "judge", "running", f"Judged sub-question {si + 1} of {len(sub_questions)}", done=si + 1, total=len(sub_questions),
                        sufficient=bool(cov.get("sufficient")), judgeUsed=cov.get("judge_used"), sufficientSoFar=sum(1 for c in coverage.values() if c.get("sufficient")))
        cov_row = {"query_id": qid, "sub_question_id": sq.id, **cov}
        cov_rows.append(cov_row)
        all_rows.extend(rows)
        if overlap:
            _store_subquestion(qid, sq, si, len(sub_questions), rows, cov_row)

        logger.info("Sub-question '%s': %d digests (%d from full text), %d verified findings, coverage sufficient=%s",
                    sq.main_topic[:50], len(rows),
                    sum(1 for r in rows if r["evidence_level"] == "full_text"),
                    sum(r["verified_count"] for r in rows), cov["sufficient"])
        if cov.get("uncovered_aspects"):
            logger.info("  Uncovered aspects: %s", cov["uncovered_aspects"])
        if cov.get("judge_used") is not None:
            logger.info("  Judge used: %s, stats: %s", cov.get("judge_used"), cov.get("judge_stats"))
        if cov.get("fallback_reason"):
            logger.warning("  Judge fallback: %s", cov.get("fallback_reason"))

    if loop2.enabled():
        progress.report(qid, "summarizer", "loop2", "completed", "Loop 2 finished",
                        searched=sum(((c.get("judge_stats") or {}).get("loop2") or {}).get("searched", 0) for c in coverage.values()),
                        covered=sum(((c.get("judge_stats") or {}).get("loop2") or {}).get("covered", 0) for c in coverage.values()))
    progress.report(qid, "summarizer", "judge", "completed", f"{sum(1 for c in coverage.values() if c.get('sufficient'))} of {len(sub_questions)} sub-questions have enough evidence",
                    done=len(sub_questions), total=len(sub_questions), sufficientSubQuestions=sum(1 for c in coverage.values() if c.get("sufficient")))
    progress.report(qid, "summarizer", "store", "running", "Saving the digests and coverage", digests=len(all_rows))
    if not overlap:                                 # with STAGE4_OVERLAP every sub-question was stored as soon as it was finished
        db_service.write_digests(all_rows)
        db_service.write_coverage(cov_rows)
    progress.report(qid, "summarizer", "store", "completed", f"Saved {len(all_rows)} digests", stored=len(all_rows))
    return {"digests": all_rows, "coverage": coverage}