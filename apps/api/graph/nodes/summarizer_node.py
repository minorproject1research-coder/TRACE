import logging
import os
from concurrent.futures import ThreadPoolExecutor

from apps.api.graph.state import SharedResearchState
from apps.api.agents.stage3_summarizer import chunk_selector, digest_generator, coverage_check
from apps.api.services import db_service, groq_pool, llm_service

logger = logging.getLogger("apps.api.agents.stage3_summarizer")

# keep small for the first run (free-tier API limits); raise to 8 and 5 later
MAX_PAPERS, MAX_WEB = 3, 2


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
        for p in db_service.get_papers_for_stage3(qid, sq.id)[:MAX_PAPERS]:
            selected = chunk_selector.select_chunks(sq.main_topic, chunk_selector.build_chunks(p))
            level = "full_text" if p.get("has_full_text") else "abstract"
            jobs.append((si, "paper", p, selected, p.get("combined_score"), level))
        for w in db_service.get_web_sources_for_stage3(sq.id)[:MAX_WEB]:
            snippet = w.get("snippet") or ""
            if len(snippet) < 200:
                continue
            jobs.append((si, "web", w, [(0, snippet)], w.get("reliability_score"), "web_snippet"))

    # 2. Run the digests in parallel (Groq calls; the pool spreads them over the keys and waits out 429s).
    def run(job):
        si, _, _, selected, _, _ = job
        return digest_generator.generate_digest(sub_questions[si].main_topic, selected) if selected else []

    workers = _workers()
    logger.info("Stage 3: %d digests for %d sub-questions, %d worker(s), %d Groq key(s)",
                len(jobs), len(sub_questions), workers, groq_pool.key_count() if llm_service.BACKEND == "groq" else 0)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        findings_per_job = list(pool.map(run, jobs))        # keeps the job order

    # 3. Assemble rows and coverage per sub-question, in the original order.
    all_rows, cov_rows, coverage = [], [], {}
    for si, sq in enumerate(sub_questions):
        rows = [_row(qid, sq.id, st, src, findings, weight, level)
                for (j_si, st, src, _, weight, level), findings in zip(jobs, findings_per_job) if j_si == si]
        cov = coverage_check.check_coverage(sq.detail_questions, rows)
        coverage[sq.id] = cov
        cov_rows.append({"query_id": qid, "sub_question_id": sq.id, **cov})
        all_rows.extend(rows)

        logger.info("Sub-question '%s': %d digests (%d from full text), %d verified findings, coverage sufficient=%s",
                    sq.main_topic[:50], len(rows),
                    sum(1 for r in rows if r["evidence_level"] == "full_text"),
                    sum(r["verified_count"] for r in rows), cov["sufficient"])

    db_service.write_digests(all_rows)
    db_service.write_coverage(cov_rows)
    return {"digests": all_rows, "coverage": coverage}
