import logging
from apps.api.graph.state import SharedResearchState
from apps.api.agents.stage4_factcheck import fact_checker, contradiction_detector
from apps.api.services import db_service

logger = logging.getLogger("apps.api.agents.stage4_factcheck")

REPLAN_RATIO = 0.9  # LOOP 3 trigger (flag only, the loop is not built yet)


def run_factcheck(query_id: str, sub_questions) -> tuple[list[dict], dict]:
    """sub_questions: any objects with .id and .main_topic (SubQuestion models or SimpleNamespace)."""
    all_claims, all_disagreements, summary = [], [], {}

    for sq in sub_questions:
        digests = db_service.get_digests_for_stage4(query_id, sq.id)
        claims = fact_checker.load_claims(digests)
        clusters = fact_checker.verify_support(fact_checker.build_clusters(claims))
        conflicts, disagreements = contradiction_detector.detect(clusters)
        labeled = fact_checker.label_clusters(clusters, conflicts)

        for r in labeled:
            r.update({"query_id": query_id, "sub_question_id": sq.id})
        for d in disagreements:
            d.update({"query_id": query_id, "sub_question_id": sq.id})

        counts = {l: sum(1 for r in labeled if r["label"] == l)
                  for l in ("supported", "contradicted", "unverified")}
        total = len(labeled)
        summary[sq.id] = {
            **counts,
            "total": total,
            "contested": sum(1 for r in labeled if r["contested"]),
            "missing_evidence": db_service.get_missing_evidence(sq.id),
            "needs_replan": total == 0 or (counts["unverified"] + counts["contradicted"]) / total > REPLAN_RATIO,
        }
        all_claims.extend(labeled)
        all_disagreements.extend(disagreements)
        logger.info("Sub-question '%s': %d digests, %d claims %s, %d disagreements",
                    str(sq.main_topic)[:50], len(digests), total, counts, len(disagreements))

    db_service.write_fact_claims(query_id, all_claims)
    db_service.write_contradictions(query_id, all_disagreements)
    return all_claims, summary


def factcheck_node(state: SharedResearchState) -> dict:
    claims, summary = run_factcheck(state.task_plan.query_id, state.task_plan.sub_questions)
    return {"fact_claims": claims, "fact_summary": summary}