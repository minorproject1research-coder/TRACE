import logging
import os
import re
import json
from concurrent.futures import ThreadPoolExecutor

from apps.api.graph.state import SharedResearchState
from apps.api.agents.stage3_summarizer import (
    chunk_selector,
    digest_generator,
    coverage_check,
    detail_aspects,
    evidence_judge,
)
from apps.api.services import db_service, groq_pool, llm_service

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


def _row(query_id, sq_id, source_type, src, findings, weight, evidence_level):
    return {
        "query_id": query_id,
        "sub_question_id": sq_id,
        "source_type": source_type,
        "source_id": str(src["id"]),
        "source_title": src.get("title"),
        "findings": findings,
        "verified_count": sum(1 for f in findings if f["verified"]),
        "total_count": len(findings),
        "weight": weight,
        "model": llm_service.MODEL_NAME,
        "evidence_level": evidence_level,       # full_text | abstract | web_snippet
    }


def summarizer_node(state: SharedResearchState) -> dict:
    qid = state.task_plan.query_id
    sub_questions = state.task_plan.sub_questions

    # 1. Prepare every digest job locally (chunking and embedding are fast); no model call yet.
    jobs = []           # (sub_question index, source_type, source, selected chunks, weight, evidence level)
    for si, sq in enumerate(sub_questions):
        cleaned_topic = _clean_topic(sq.main_topic)
        original_details = sq.detail_questions
        
        # Split details into aspects
        aspects, aspect_to_detail = detail_aspects.flatten_aspects(
            original_details, sq.id, cleaned_topic
        )
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

    # 2. Run the digests in parallel (Groq calls; the pool spreads them over the keys and waits out 429s).
    def run(job):
        si, _, _, selected, _, _, aspects, original_details, aspect_to_detail = job
        if not selected:
            return [], 0
        
        # Retry once on JSON parse failure
        digest_failures = 0
        for attempt in range(2):
            try:
                findings = digest_generator.generate_digest(
                    sub_questions[si].main_topic,
                    selected,
                    detail_aspects=aspects,
                    main_topic=_clean_topic(sub_questions[si].main_topic),
                )
                return findings, digest_failures
            except json.JSONDecodeError as e:
                digest_failures += 1
                logger.warning(f"Digest JSON parse failed (attempt {attempt + 1}/2): {e}")
                if attempt == 0:
                    continue
                logger.error(f"Digest generation failed after 2 attempts for sub-question {sub_questions[si].id}")
                return [], digest_failures
            except Exception as e:
                logger.error(f"Digest generation failed: {e}")
                return [], digest_failures
        return [], digest_failures

    workers = _workers()
    logger.info("Stage 3: %d digests for %d sub-questions, %d worker(s), %d Groq key(s)",
                len(jobs), len(sub_questions), workers, groq_pool.key_count() if llm_service.BACKEND == "groq" else 0)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(run, jobs))
    findings_per_job = [r[0] for r in results]
    digest_failures_per_job = [r[1] for r in results]

    # 3. Assemble rows and coverage per sub-question, in the original order.
    all_rows, cov_rows, coverage = [], [], {}
    for si, sq in enumerate(sub_questions):
        rows = [_row(qid, sq.id, st, src, findings, weight, level)
                for (j_si, st, src, _, weight, level, _, _, _), findings in zip(jobs, findings_per_job) if j_si == si]
        
        # Get aspects and mapping for this sub-question
        cleaned_topic = _clean_topic(sq.main_topic)
        aspects, aspect_to_detail = detail_aspects.flatten_aspects(
            sq.detail_questions, sq.id, cleaned_topic
        )
        
        # Build chunk_lookup for judge context
        chunk_lookup = {}
        for (j_si, st, src, selected, weight, level, _, _, _), findings in zip(jobs, findings_per_job):
            if j_si != si:
                continue
            for chunk_id, chunk_text in selected:
                chunk_lookup[str(chunk_id)] = chunk_text
        
        # Run judge for this sub-question if there are verified findings
        judge_verdicts = {}
        has_verified = any(f.get("verified") for r in rows for f in r.get("findings", []))
        if has_verified and aspects:
            candidates, judge_verdicts = evidence_judge.run_judge_for_subquestion(
                aspects, rows, chunk_lookup
            )
        
        # Judge-based coverage with fallback
        cov = coverage_check.check_coverage_judged(
            aspects, aspect_to_detail, sq.detail_questions, rows, judge_verdicts
        )
        # Add digest failures count
        sq_failures = sum(digest_failures_per_job[i] for i, (j_si, _, _, _, _, _, _, _, _) in enumerate(jobs) if j_si == si)
        cov["digest_failures"] = sq_failures
        
        coverage[sq.id] = cov
        cov_rows.append({"query_id": qid, "sub_question_id": sq.id, **cov})
        all_rows.extend(rows)

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

    db_service.write_digests(all_rows)
    db_service.write_coverage(cov_rows)
    return {"digests": all_rows, "coverage": coverage}