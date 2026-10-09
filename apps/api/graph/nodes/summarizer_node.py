import logging
from apps.api.graph.state import SharedResearchState
from apps.api.agents.stage3_summarizer import chunk_selector, digest_generator, coverage_check
from apps.api.services import db_service, llm_service

logger = logging.getLogger("apps.api.agents.stage3_summarizer")

# keep small for the first run (free-tier API limits); raise to 8 and 5 later
MAX_PAPERS, MAX_WEB = 3, 2


def _row(query_id, sq_id, source_type, src, findings, weight):
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
    }


def summarizer_node(state: SharedResearchState) -> dict:
    qid = state.task_plan.query_id
    all_rows, cov_rows, coverage = [], [], {}

    for sq in state.task_plan.sub_questions:
        rows = []

        for p in db_service.get_papers_for_stage3(qid, sq.id)[:MAX_PAPERS]:
            selected = chunk_selector.select_chunks(sq.main_topic, chunk_selector.build_chunks(p))
            findings = digest_generator.generate_digest(sq.main_topic, selected) if selected else []
            rows.append(_row(qid, sq.id, "paper", p, findings, p.get("combined_score")))

        for w in db_service.get_web_sources_for_stage3(sq.id)[:MAX_WEB]:
            snippet = w.get("snippet") or ""
            if len(snippet) < 200:
                continue
            findings = digest_generator.generate_digest(sq.main_topic, [(0, snippet)])
            rows.append(_row(qid, sq.id, "web", w, findings, w.get("reliability_score")))

        cov = coverage_check.check_coverage(sq.detail_questions, rows)
        coverage[sq.id] = cov
        cov_rows.append({"query_id": qid, "sub_question_id": sq.id, **cov})
        all_rows.extend(rows)

        logger.info("Sub-question '%s': %d digests, %d verified findings, coverage sufficient=%s",
                    sq.main_topic[:50], len(rows),
                    sum(r["verified_count"] for r in rows), cov["sufficient"])

    db_service.write_digests(all_rows)
    db_service.write_coverage(cov_rows)
    return {"digests": all_rows, "coverage": coverage}