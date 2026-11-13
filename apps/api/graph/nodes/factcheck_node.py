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
  STAGE4_OVERLAP=true         Stage 4 of a sub-question starts as soon as Stage 3 has stored it (see start_in_background / collect below)

A sub-question that fails (a database or model error) is reported in the summary and skipped; Stage 4 never fails the run: the evidence of
Stage 3 is already stored. `needs_replan` is only recorded (the replan loop, LOOP 3, is not built).
"""
import logging
import contextvars
import os
import threading
from concurrent.futures import CancelledError, ThreadPoolExecutor

from apps.api import config
from apps.api.agents.stage4_factcheck import fact_checker, contradiction_detector, judge
from apps.api.graph.state import SharedResearchState
from apps.api.services import db_service, progress

logger = logging.getLogger("apps.api.agents.stage4_factcheck")

REPLAN_RATIO = 0.9  # LOOP 3 trigger (flag only, the loop is not built yet)


def enabled() -> bool:
    return config.factcheck_enabled()


def _parallel_steps() -> bool:
    """STAGE4_PARALLEL_STEPS (default true): the near-match judge and the conflict NLI of one sub-question run side by side."""
    return os.getenv("STAGE4_PARALLEL_STEPS", "true").strip().lower() not in ("0", "false", "no", "off")


def _sq_workers() -> int:
    """STAGE4_SQ_WORKERS (default 1): how many sub-questions Stage 4 checks at the same time when it overlaps Stage 3. 1 = one after the other
    (the old behaviour). 2 shortens the queue behind the last sub-question but doubles the Groq and CPU load (STAGE4_WORKERS judge threads each)."""
    try:
        return max(1, int(os.getenv("STAGE4_SQ_WORKERS", "2")))
    except ValueError:
        return 1


def _worker_no():
    """1-based number of the Stage 4 worker thread that runs this sub-question ("stage4-overlap_0" -> 1), None when it is not a worker thread."""
    name = threading.current_thread().name
    if name.startswith("stage4-overlap_"):
        try:
            return int(name.rsplit("_", 1)[-1]) + 1
        except ValueError:
            return None
    return None


def _check_sub_question(query_id: str, sq, report) -> tuple[list[dict], list[dict], dict]:
    with judge.track() as jt:
        return _check_sub_question_counted(query_id, sq, report, jt)


def _check_sub_question_counted(query_id: str, sq, report, jt: dict) -> tuple[list[dict], list[dict], dict]:
    digests = db_service.get_digests_for_stage4(query_id, sq.id)
    report("claims", f"Reading the claims of {len(digests)} sources", sources=len(digests), worker=_worker_no())
    claims = fact_checker.load_claims(digests)
    report("clusters", f"Grouping {len(claims)} claims that say the same thing", claims=len(claims))
    clusters = fact_checker.build_clusters(claims)
    report("support", f"Checking that the quotes support {len(clusters)} grouped claims", clusters=len(clusters))
    clusters = fact_checker.verify_support(clusters)
    report("near", "Looking for close variants of single-source claims in other documents")
    if _parallel_steps() and fact_checker.NEAR_ON:
        # the near-match judge waits on Groq, the conflict step computes NLI on the CPU: they use different resources, read the same clusters
        # and write different fields, so they run side by side (the clusters of the near step are only read by the label step after both)
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="stage4-near") as pool:
            near = pool.submit(contextvars.copy_context().run, fact_checker.find_near_matches, clusters)
            report("conflicts", "Looking for sources that disagree")
            try:
                conflicts, disagreements = contradiction_detector.detect(clusters)
            finally:
                near.result()
    else:
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
        "judge_calls": jt["calls"],
        "judge_cache_hits": jt["cache_hits"],
        "judge_waits": jt["waits"],
        "judge_failures": jt["failures"] + jt["skipped"],
        "support_from_stage3": sum(1 for r in labeled for e in r["evidence"] if e.get("via") == "stage3_judge"),
        "missing_evidence": db_service.get_missing_evidence(sq.id),
        "needs_replan": total == 0 or (counts["unverified"] + counts["contradicted"]) / total > REPLAN_RATIO,
    }
    logger.info("Sub-question '%s': %d digests, %d claims -> %d clusters %s, %d disagreements",
                str(sq.main_topic)[:50], len(digests), len(claims), total, counts, len(disagreements))
    report("done", f"Checked {total} claims", claims=total, **counts, disagreements=len(disagreements), judgeCalls=summary["judge_calls"],
           judgeCacheHits=summary["judge_cache_hits"], judgeWaits=summary["judge_waits"], judgeFailures=summary["judge_failures"], worker=_worker_no())
    return labeled, disagreements, summary


def _check_one(query_id: str, sq, report) -> tuple[list[dict], list[dict], dict]:
    """_check_sub_question that never raises: a sub-question that fails is logged and gives ([], [], {"error": ...}), so nothing is
    written for it and the others go on."""
    try:
        return _check_sub_question(query_id, sq, report)
    except Exception as e:
        logger.exception("Stage 4 failed for sub-question '%s'", str(getattr(sq, "main_topic", ""))[:60])
        return [], [], {"error": f"{type(e).__name__}: {str(e)[:200]}"}


# ---------------------------------------------------------------------------------------------------- overlap with Stage 3
# STAGE4_OVERLAP (default true, only with FACTCHECK=true): the summarizer hands every sub-question to start_in_background() as soon as
# its digests and coverage are stored, so Stage 4 of sub-question 1 runs while Stage 3 still judges sub-question 2. factcheck_node then
# only waits for the futures (collect), starts any sub-question that was not started, and writes the results as before.
#
# One worker by default (STAGE4_SQ_WORKERS=1): the NLI model uses all CPU cores, so two NLI steps at once are not faster (they take turns
# on the model lock; the Groq judges of the other sub-question can still run meanwhile). With 2 the queue behind the last sub-question
# is shorter. The judge counters of a sub-question are counted per job (judge.track), so they stay exact with any number of workers.
_overlaps: dict[str, "_Overlap"] = {}
_expected: set[str] = set()         # runs of the graph (the planner announced them): only these may start Stage 4 early
_overlaps_lock = threading.Lock()
_worker: ThreadPoolExecutor | None = None
_worker_size = 0


def _executor() -> ThreadPoolExecutor:
    """The shared pool; made again (the old one finishes its jobs, then ends) when STAGE4_SQ_WORKERS changed since it was made."""
    global _worker, _worker_size
    size = _sq_workers()
    with _overlaps_lock:
        if _worker is None or _worker_size != size:
            if _worker is not None:
                _worker.shutdown(wait=False)
            _worker = ThreadPoolExecutor(max_workers=size, thread_name_prefix="stage4-overlap")
            _worker_size = size
        return _worker


def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class _Cancelled(Exception):
    """The run was discarded (Stage 3 failed): the running Stage 4 job stops before its next step instead of spending Groq calls."""


class _Overlap:
    """The Stage 4 jobs of one run that started during Stage 3. Their progress reports are held back until the factcheck node starts
    (go_live), so the UI sees the factcheck stage start first and its steps afterwards, never steps of a stage that has not begun."""
    def __init__(self, query_id: str):
        self.query_id = query_id
        self.futures: dict = {}                                 # sub-question id -> Future of (labeled, disagreements, summary)
        self.cancelled = False                                  # set by discard(): a job that is running stops at its next step boundary
        self.live = False
        self.held: list[tuple] = []
        self.lock = threading.Lock()

    def report(self, step: str, message: str, subquestion: int, total: int, data: dict) -> None:
        if self.cancelled:
            raise _Cancelled()              # raised inside _check_sub_question at a step boundary; _check_one turns it into an error result
        with self.lock:                                         # inside the lock, so a replay and a live report keep their order
            if self.live:
                progress.report(self.query_id, "factcheck", step, "running", message, subQuestion=subquestion, subQuestions=total, **data)
            else:
                self.held.append((step, message, subquestion, total, data, _utc_now()))

    def go_live(self) -> None:
        with self.lock:
            held, self.held, self.live = self.held, [], True
            for step, message, subquestion, total, data, at in held:
                progress.report(self.query_id, "factcheck", step, "running", message, subQuestion=subquestion, subQuestions=total, occurredAt=at, **data)


def expect(query_id: str) -> None:
    """Called by the planner of a graph run with Stage 4 on. A direct call of summarizer_node (the dev scripts, a stored-run audit) never
    passes the planner, so it is not expected and its Stage 3 does not queue Stage 4 jobs that nothing would collect."""
    with _overlaps_lock:
        _expected.add(query_id)


def is_expected(query_id: str) -> bool:
    with _overlaps_lock:
        return query_id in _expected


def overlap_started(query_id: str) -> bool:
    with _overlaps_lock:
        return query_id in _overlaps


def start_in_background(query_id: str, sq, index: int, total: int) -> bool:
    """Queue Stage 4 of one sub-question on the single worker (index: its 1-based place among `total`, for the progress reports). Called by
    the summarizer once the sub-question's digests and coverage are stored. Never raises; False means it was not queued (factcheck_node then
    checks that sub-question itself)."""
    try:
        with _overlaps_lock:
            overlap = _overlaps.setdefault(query_id, _Overlap(query_id))
            if sq.id in overlap.futures:
                return True
        report = lambda step, message, **data: overlap.report(step, message, index, total, data)
        future = _executor().submit(_check_one, query_id, sq, report)
        with _overlaps_lock:
            overlap.futures[sq.id] = future
        return True
    except Exception:
        logger.exception("could not start Stage 4 early for sub-question '%s'", str(getattr(sq, "main_topic", ""))[:60])
        return False


def activate(query_id: str) -> None:
    """The factcheck node has started: release the progress reports that were held back, report live from now on."""
    with _overlaps_lock:
        overlap = _overlaps.get(query_id)
    if overlap is not None:
        overlap.go_live()


def discard(query_id: str, keep_expected: bool = False) -> None:
    """Forget the early Stage 4 jobs of a run (the summarizer failed, or the results were collected). Jobs that did not start are
    cancelled; one that is running stops at its next step boundary (its result is dropped)."""
    with _overlaps_lock:
        overlap = _overlaps.pop(query_id, None)
        if not keep_expected:
            _expected.discard(query_id)
    if overlap is not None:
        overlap.cancelled = True
        for future in list(overlap.futures.values()):
            future.cancel()


def collect(query_id: str, sub_questions) -> list[tuple[list[dict], list[dict], dict]] | None:
    """None when nothing was started early for this run. Otherwise one (labeled, disagreements, summary) per sub-question in the order of
    `sub_questions`: waits for the running jobs and checks any sub-question that was not started early (same code, same worker)."""
    with _overlaps_lock:
        overlap = _overlaps.get(query_id)
    if overlap is None:
        return None
    try:
        overlap.go_live()
        n = len(sub_questions)
        for si, sq in enumerate(sub_questions, 1):
            if sq.id not in overlap.futures:
                start_in_background(query_id, sq, si, n)
        results = []
        for sq in sub_questions:
            future = overlap.futures.get(sq.id)
            if future is None:
                results.append(([], [], {"error": "RuntimeError: Stage 4 could not be started for this sub-question"}))
                continue
            try:
                results.append(future.result())
            except (Exception, CancelledError) as e:                    # _check_one does not raise; this is the cancelled or broken-pool case
                logger.error("Stage 4 job of sub-question '%s' gave no result: %s", str(getattr(sq, "main_topic", ""))[:60], type(e).__name__)
                results.append(([], [], {"error": f"{type(e).__name__}: {str(e)[:200]}"}))
        return results
    finally:
        discard(query_id)


def run_factcheck(query_id: str, sub_questions) -> tuple[list[dict], dict]:
    """sub_questions: any objects with .id and .main_topic (SubQuestion models or SimpleNamespace). Returns (all claims, summary per
    sub-question id). A sub-question that raises is logged and summarised as {"error": ...}; nothing is written for it.
    Sub-questions that the summarizer already queued (STAGE4_OVERLAP) are only waited for, the others are checked here, one after the other."""
    all_claims, all_disagreements, summary = [], [], {}
    n = len(sub_questions)
    results = collect(query_id, sub_questions)
    if results is None:
        results = []
        for si, sq in enumerate(sub_questions, 1):
            def report(step, message, _si=si, **data):
                progress.report(query_id, "factcheck", step, "running", message, subQuestion=_si, subQuestions=n, **data)
            results.append(_check_one(query_id, sq, report))
    for sq, (labeled, disagreements, sq_summary) in zip(sub_questions, results):
        summary[sq.id] = sq_summary
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
    activate(qid)                           # with STAGE4_OVERLAP: the steps that Stage 4 already did during Stage 3 are reported now, in order
    try:
        claims, summary = run_factcheck(qid, state.task_plan.sub_questions)
    except Exception as e:                  # e.g. the database stayed unreachable at the final write; Stage 3's evidence is already stored
        logger.exception("Stage 4 failed")
        discard(qid)
        progress.report(qid, "factcheck", "store", "failed", f"Fact checking failed: {type(e).__name__}")
        return {"fact_summary": {"error": f"{type(e).__name__}: {str(e)[:200]}"}}
    counts = {l: sum(1 for c in claims if c["label"] == l) for l in fact_checker.LABELS}
    progress.report(qid, "factcheck", "store", "completed", f"{len(claims)} claims checked", claims=len(claims), **counts)
    return {"fact_claims": claims, "fact_summary": summary}
