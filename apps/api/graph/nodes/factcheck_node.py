"""Stage 4 as a graph node: checks the claims of Stage 3 across sources.

For every sub-question: the digests of the newest Stage 3 run -> claims -> clusters of claims that state the same thing -> which quotes
really support their claim -> a close variant in another document? -> conflicts between clusters -> a label per cluster: supported (two
independent documents), partially_supported (one document, plus a close variant of the claim in another), contradicted, or
unverified (rests on one document, which says nothing about whether it is true). Results go to `fact_claims` and `contradictions`.

  FACTCHECK=false             switch (default off: it adds several hundred LLM calls per run, see docs/KNOWN_LIMITS.md)
  STAGE4_WORKERS=4            judge calls in parallel
  STAGE4_NEAR=true            the partially_supported label (one extra judge call per candidate pair; STAGE4_MAX_NEAR_JUDGE caps them)
  STAGE4_MAX_MERGE_JUDGE / STAGE4_MAX_SUPPORT_JUDGE / STAGE4_MAX_JUDGE / STAGE4_MAX_PAIRS   caps per sub-question (a warning is logged when one bites)
  STAGE4_CACHE=true           judge answers are cached on disk, a rerun costs no LLM calls

A sub-question that fails (a database or model error) is reported in the summary and skipped; Stage 4 never fails the run: the evidence of
Stage 3 is already stored. `needs_replan` is only recorded (the replan loop, LOOP 3, is not built).
"""
import logging

from apps.api import config
from apps.api.agents.stage4_factcheck import fact_checker, contradiction_detector, judge
from apps.api.graph.state import SharedResearchState
from apps.api.services import db_service, progress

logger = logging.getLogger("apps.api.agents.stage4_factcheck")

REPLAN_RATIO = 0.9  # LOOP 3 trigger (flag only, the loop is not built yet)


def enabled() -> bool:
    return config.factcheck_enabled()


def _check_sub_question(query_id: str, sq, report) -> tuple[list[dict], list[dict], dict]:
    j0 = judge.stats()
    digests = db_service.get_digests_for_stage4(query_id, sq.id)
    report("claims", f"Reading the claims of {len(digests)} sources", sources=len(digests))
    claims = fact_checker.load_claims(digests)
    report("clusters", f"Grouping {len(claims)} claims that say the same thing", claims=len(claims))
    clusters = fact_checker.build_clusters(claims)
    report("support", f"Checking that the quotes support {len(clusters)} grouped claims", clusters=len(clusters))
    clusters = fact_checker.verify_support(clusters)
    report("near", "Looking for close variants of single-source claims in other documents")
    clusters = fact_checker.find_near_matches(clusters)
    report("conflicts", "Looking for sources that disagree")
    conflicts, disagreements = contradiction_detector.detect(clusters)
    labeled = fact_checker.label_clusters(clusters, conflicts)

    for r in labeled:
        r.update({"query_id": query_id, "sub_question_id": sq.id})
    for d in disagreements:
        d.update({"query_id": query_id, "sub_question_id": sq.id})

    counts = {l: sum(1 for r in labeled if r["label"] == l) for l in fact_checker.LABELS}
    total = len(labeled)
    summary = {
        **counts,
        "total": total,
        "digests": len(digests),
        "claims_loaded": len(claims),
        "contested": sum(1 for r in labeled if r["contested"]),
        "disagreements": len(disagreements),
        "judge_calls": judge.stats()["calls"] - j0["calls"],
        "judge_cache_hits": judge.stats()["cache_hits"] - j0["cache_hits"],
        "judge_waits": judge.stats()["waits"] - j0["waits"],
        "judge_failures": judge.stats()["failures"] - j0["failures"] + judge.stats()["skipped"] - j0["skipped"],
        "support_from_stage3": sum(1 for r in labeled for e in r["evidence"] if e.get("via") == "stage3_judge"),
        "missing_evidence": db_service.get_missing_evidence(sq.id),
        "needs_replan": total == 0 or (counts["unverified"] + counts["contradicted"]) / total > REPLAN_RATIO,
    }
    logger.info("Sub-question '%s': %d digests, %d claims -> %d clusters %s, %d disagreements",
                str(sq.main_topic)[:50], len(digests), len(claims), total, counts, len(disagreements))
    return labeled, disagreements, summary


def run_factcheck(query_id: str, sub_questions) -> tuple[list[dict], dict]:
    """sub_questions: any objects with .id and .main_topic (SubQuestion models or SimpleNamespace). Returns (all claims, summary per
    sub-question id). A sub-question that raises is logged and summarised as {"error": ...}; nothing is written for it."""
    all_claims, all_disagreements, summary = [], [], {}
    n = len(sub_questions)
    for si, sq in enumerate(sub_questions, 1):
        def report(step, message, **data):
            progress.report(query_id, "factcheck", step, "running", message, subQuestion=si, subQuestions=n, **data)
        try:
            labeled, disagreements, summary[sq.id] = _check_sub_question(query_id, sq, report)
        except Exception as e:
            logger.exception("Stage 4 failed for sub-question '%s'", str(getattr(sq, "main_topic", ""))[:60])
            summary[sq.id] = {"error": f"{type(e).__name__}: {str(e)[:200]}"}
            continue
        all_claims.extend(labeled)
        all_disagreements.extend(disagreements)

    progress.report(query_id, "factcheck", "store", "running", "Saving the fact-check results", claims=len(all_claims), disagreements=len(all_disagreements))
    db_service.write_fact_claims(query_id, all_claims)
    db_service.write_contradictions(query_id, all_disagreements)
    return all_claims, summary


def factcheck_node(state: SharedResearchState) -> dict:
    if not enabled():
        return {}
    qid = state.task_plan.query_id
    progress.report(qid, "factcheck", "branch", "running", "Checking claims across sources")
    try:
        claims, summary = run_factcheck(qid, state.task_plan.sub_questions)
    except Exception as e:                  # e.g. the database stayed unreachable at the final write; Stage 3's evidence is already stored
        logger.exception("Stage 4 failed")
        progress.report(qid, "factcheck", "store", "failed", f"Fact checking failed: {type(e).__name__}")
        return {"fact_summary": {"error": f"{type(e).__name__}: {str(e)[:200]}"}}
    counts = {l: sum(1 for c in claims if c["label"] == l) for l in fact_checker.LABELS}
    progress.report(qid, "factcheck", "store", "completed", f"{len(claims)} claims checked", claims=len(claims), **counts)
    return {"fact_claims": claims, "fact_summary": summary}
