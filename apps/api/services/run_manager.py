"""Runs of the research graph for the API: a queue, a worker thread per concurrent run, and an event log per run.

A run is the whole graph (planner -> paper retrieval + web search in parallel -> summarizer -> fact check -> written report), started in a background thread because it
takes 15-25 minutes. The run id IS the research query id (SharedResearchState.query_id), so a finished run can be read from the database
after a server restart. Progress is the stream of node updates of the graph (stream_mode="updates"), turned into events:

  run_queued, run_started, stage_started, branch_started, step, branch_completed, stage_completed, run_completed, run_failed

branch_started and step come from INSIDE the nodes (services/progress.py): the paper and web branches run at the same time, and each reports its
steps (search, relevance judge, scoring, store, parsing; digest and evidence judge in the summarizer) with small counts.

Stages the UI should show: planner, retrieval (papers + web), summarizer, factcheck (only when FACTCHECK=true, otherwise "not_run"),
report (Stage 5, the written report: only when STAGE5=true, otherwise "not_run"; a failure marks the stage "failed", never the run).
State lives in memory (events, status); everything a report needs is in the database.
"""
import logging
import os
import threading
import traceback
import uuid
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable, Optional

from apps.api import config
from apps.api.services import groq_pool, progress

logger = logging.getLogger("apps.api.run_manager")

STAGES = ("planner", "retrieval", "summarizer", "factcheck", "report")
NOT_BUILT = ()                              # every stage is built now ("factcheck" and "report" are "not_run" per run when their switch is off)
NODE_STAGE = {"planner": "planner", "paper_retrieval": "retrieval", "web_search": "retrieval", "summarizer": "summarizer", "factcheck": "factcheck", "report": "report"}
BRANCH = {"paper_retrieval": "papers", "web_search": "web"}
LANE_STAGE = {"papers": "retrieval", "web": "retrieval", "summarizer": "summarizer", "factcheck": "factcheck", "report": "report"}
TERMINAL = ("run_completed", "run_failed")


class QueueFull(Exception):
    """Too many runs are waiting."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _switched_off(stage: str) -> bool:
    """The stages that run only when their switch is on: factcheck (FACTCHECK) and report (STAGE5)."""
    if stage == "factcheck":
        return not config.factcheck_enabled()
    if stage == "report":
        from apps.api.agents.stage5_report import settings as stage5       # light: only reads the environment
        return not stage5.stage5_enabled()
    return False


class RunRecord:
    def __init__(self, run_id: str, question: str):
        self.id, self.question = run_id, question
        self.status = "pending"
        self.created_at, self.started_at, self.finished_at = _now(), None, None
        self.error: Optional[str] = None
        self.stages = {s: ("not_built" if s in NOT_BUILT else "not_run" if _switched_off(s) else "pending") for s in STAGES}
        self.events: list[dict] = []
        self._lock = threading.Lock()
        self.usage_before: Optional[dict] = None        # Groq meter snapshot taken when the run starts (the usage of the run = the meter now minus this)

    def groq(self, by_purpose: bool = False) -> Optional[dict]:
        """Groq use of this run SO FAR (cumulative): tokens, calls, rate limits and the key-seconds spent waiting for them. None when switched off
        (RUN_TELEMETRY=false) or not started. Never raises."""
        if self.usage_before is None or os.getenv("RUN_TELEMETRY", "true").strip().lower() in ("0", "false", "no", "off"):
            return None
        try:
            used = groq_pool.meter.since(self.usage_before)
            t = used["totals"]
            out = {"tokens": t.get("total", 0), "calls": t.get("calls", 0), "rateLimits": t.get("rate_limited", 0), "parkedSeconds": t.get("parked_seconds", 0)}
            if by_purpose:
                out["byPurpose"] = {p: c.get("total", 0) for p, c in used["by_purpose"].items()}
            return out
        except Exception:
            return None

    @property
    def finished(self) -> bool:
        return self.status in ("completed", "failed")

    def emit(self, event: str, stage: Optional[str] = None, status: Optional[str] = None, message: str = "", data: Optional[dict] = None) -> dict:
        with self._lock:
            ev = {"seq": len(self.events), "event": event, "stage": stage, "status": status, "message": message,
                  "data": data or {}, "timestamp": _now()}
            self.events.append(ev)
            return ev

    def events_from(self, index: int) -> list[dict]:
        with self._lock:
            return self.events[index:]

    def session(self) -> dict:
        return {"id": self.id, "question": self.question, "status": self.status, "createdAt": self.created_at,
                "startedAt": self.started_at, "finishedAt": self.finished_at, "error": self.error,
                "stages": dict(self.stages)}


# ------------------------------------------------------------------------------------------------ what the graph updates mean
def _count(x) -> int:
    try:
        return len(x)
    except TypeError:
        return 0


def summarize_update(node: str, update: dict) -> tuple[str, dict]:
    """A short message and a few numbers for one node's finished update. Never raises: a surprise in the update shape gives an empty summary."""
    try:
        if node == "planner":
            plan = update.get("task_plan")
            subs = getattr(plan, "sub_questions", []) or []
            data = {"subQuestions": len(subs), "queries": sum(len(s.queries) for s in subs), "domainAnchor": getattr(plan, "domain_anchor", "") or None,
                    "topics": [s.main_topic for s in subs]}
            return f"Planned {data['subQuestions']} sub-questions and {data['queries']} search queries", data
        if node == "paper_retrieval":
            return f"Kept {_count(update.get('paper_results'))} papers", {"papers": _count(update.get("paper_results"))}
        if node == "web_search":
            return f"Found {_count(update.get('web_sources'))} web sources", {"webSources": _count(update.get("web_sources"))}
        if node == "summarizer":
            cov = update.get("coverage") or {}
            sufficient = sum(1 for c in cov.values() if isinstance(c, dict) and c.get("sufficient"))
            data = {"digests": _count(update.get("digests")), "subQuestions": len(cov), "sufficientSubQuestions": sufficient}
            return f"Digested {data['digests']} sources; {sufficient} of {len(cov)} sub-questions have sufficient evidence", data
        if node == "factcheck":
            claims = update.get("fact_claims") or []
            summary = update.get("fact_summary") or {}
            if summary.get("error"):
                return f"Fact checking failed: {summary['error']}", {"error": summary["error"]}
            data = {"claims": _count(claims), "subQuestions": len(summary), "failedSubQuestions": sum(1 for s in summary.values() if isinstance(s, dict) and s.get("error")),
                    **{l: sum(1 for c in claims if c.get("label") == l) for l in ("supported", "partially_supported", "unverified", "contradicted")},
                    "contested": sum(1 for c in claims if c.get("contested")),
                    "disagreements": sum(s.get("disagreements", 0) for s in summary.values() if isinstance(s, dict)),
                    "judgeFailures": sum(s.get("judge_failures", 0) for s in summary.values() if isinstance(s, dict)),
                    "judgeWaits": sum(s.get("judge_waits", 0) for s in summary.values() if isinstance(s, dict))}
            return f"Checked {data['claims']} claims: {data['supported']} supported, {data['partially_supported']} partially supported, {data['unverified']} unverified, {data['contradicted']} contradicted", data
        if node == "report":
            status = str(update.get("written_report_status") or "")
            if not status:
                return "The written report did not run", {}
            rep = update.get("written_report") or {}
            sections = rep.get("sections") or []
            data = {"status": status, "sections": _count(sections), "sentences": sum(_count(s.get("sentences")) for s in sections if isinstance(s, dict)),
                    "references": _count(rep.get("references")), "warnings": _count(rep.get("warnings"))}
            if status == "failed":
                return "The written report failed; the evidence report is still available", data
            return f"Wrote the report ({status}): {data['sections']} sections, {data['sentences']} sentences, {data['references']} references", data
    except Exception:                                   # a summary must never break a run
        logger.exception("could not summarize the update of node %s", node)
    return "", {}


class RunManager:
    def __init__(self, graph_factory: Optional[Callable] = None, max_workers: Optional[int] = None, max_pending: Optional[int] = None):
        self._graph_factory = graph_factory or self._default_graph
        self._graph = None
        self._graph_lock = threading.Lock()
        self._workers = max_workers or config.MAX_CONCURRENT_RUNS
        self._max_pending = config.MAX_PENDING_RUNS if max_pending is None else max_pending
        self._executor = ThreadPoolExecutor(max_workers=self._workers, thread_name_prefix="trace-run")
        self._runs: "OrderedDict[str, RunRecord]" = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def _default_graph():
        from apps.api.graph.build_graph import build_graph          # imported here: it loads langgraph and every stage
        return build_graph()

    def graph(self):
        with self._graph_lock:
            if self._graph is None:
                self._graph = self._graph_factory()
            return self._graph

    # -------------------------------------------------------------------------------------------------------- queries
    def get(self, run_id: str) -> Optional[RunRecord]:
        with self._lock:
            return self._runs.get(run_id)

    def active_count(self) -> int:
        with self._lock:
            return sum(1 for r in self._runs.values() if not r.finished)

    def recent(self, limit: int = 20) -> list[RunRecord]:
        with self._lock:
            return list(reversed(list(self._runs.values())))[:limit]

    # ------------------------------------------------------------------------------------------------------- submitting
    def submit(self, question: str) -> RunRecord:
        with self._lock:
            waiting = sum(1 for r in self._runs.values() if not r.finished)
            if waiting >= self._workers + self._max_pending:
                raise QueueFull(f"{waiting} runs are already running or queued; try again later")
            rec = RunRecord(str(uuid.uuid4()), question)
            self._runs[rec.id] = rec
            self._evict()
        rec.emit("run_queued", status="pending", message="Queued")
        self._executor.submit(self._run, rec)
        return rec

    def _evict(self) -> None:
        """Forget the oldest FINISHED runs beyond MAX_RUNS_IN_MEMORY (called with the lock held)."""
        for run_id in [i for i, r in self._runs.items() if r.finished][: max(0, len(self._runs) - config.MAX_RUNS_IN_MEMORY)]:
            del self._runs[run_id]

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    # ----------------------------------------------------------------------------------------------------------- the run
    def _stage(self, rec: RunRecord, stage: str, state: str, message: str = "", data: Optional[dict] = None) -> None:
        rec.stages[stage] = state
        g = rec.groq(by_purpose=state != "running")
        if g is not None:
            data = {**(data or {}), "groq": g}
        rec.emit("stage_started" if state == "running" else "stage_completed", stage=stage, status=state, message=message, data=data)

    @staticmethod
    def _complete(rec: RunRecord, usage_before: Optional[dict]) -> None:
        rec.status, rec.finished_at = "completed", _now()
        used = groq_pool.meter.since(usage_before)
        logger.info("run %s: %s", rec.id, groq_pool.usage_text(used))
        rec.emit("run_completed", status="completed", message="Run finished", data={"groqTokens": used["totals"].get("total", 0),
                 "groqCalls": used["totals"].get("calls", 0), "groqRateLimits": used["totals"].get("rate_limited", 0),
                 "groqParkedSeconds": used["totals"].get("parked_seconds", 0), "groqTokensByPurpose": {p: c.get("total", 0) for p, c in used["by_purpose"].items()},
                 "reportUrl": f"/api/research/{rec.id}/report", "stagesNotRun": [s for s, v in rec.stages.items() if v in ("not_built", "not_run")]})

    def _run(self, rec: RunRecord) -> None:
        from apps.api.graph.state import SharedResearchState        # lazy: keeps importing this module light
        rec.usage_before = groq_pool.meter.snapshot()       # tokens sent to Groq by THIS process during the run (runs normally do not overlap)
        rec.status, rec.started_at = "running", _now()
        rec.emit("run_started", status="running", message="Run started")
        self._stage(rec, "planner", "running", "Planning sub-questions")
        branches_done: set[str] = set()

        def on_progress(report: dict) -> None:
            """A node of this run reported a step: it becomes an event (called from the node's thread; emit() is thread-safe)."""
            lane, step, state = report["lane"], report["step"], report["state"]
            stage = LANE_STAGE.get(lane) or (report["data"].get("stage") if lane == "notes" else None)
            g = rec.groq()
            extra = {"groq": g} if g is not None else {}
            if step == "branch":
                rec.emit("branch_started", stage=stage, status=state, message=report["message"], data={"branch": lane, **report["data"]})
            else:
                rec.emit("step", stage=stage, status=state, message=report["message"], data={"lane": lane, "step": step, "state": state, **report["data"], **extra})

        progress.register(rec.id, on_progress)
        usage_before = rec.usage_before
        try:
            for chunk in self.graph().stream(SharedResearchState(raw_query=rec.question, query_id=rec.id), stream_mode="updates"):
                for node, update in (chunk or {}).items():
                    stage = NODE_STAGE.get(node)
                    if stage is None:
                        continue
                    message, data = summarize_update(node, update or {})
                    if node == "planner":
                        self._stage(rec, "planner", "completed", message, data)
                        self._stage(rec, "retrieval", "running", "Searching papers and the web")
                    elif node in BRANCH:
                        branches_done.add(node)
                        rec.emit("branch_completed", stage="retrieval", status="completed", message=message, data={"branch": BRANCH[node], **data})
                        if branches_done == set(BRANCH):
                            self._stage(rec, "retrieval", "completed", "Retrieval finished")
                            self._stage(rec, "summarizer", "running", "Reading sources and checking evidence")
                    elif node == "summarizer":
                        self._stage(rec, "summarizer", "completed", message, data)
                        if rec.stages["factcheck"] == "pending":
                            self._stage(rec, "factcheck", "running", "Checking claims across sources")
                    elif node == "factcheck":
                        if rec.stages["factcheck"] == "running":
                            self._stage(rec, "factcheck", "failed" if data.get("error") else "completed", message, data)
                        if rec.stages["report"] == "pending":           # Stage 5 starts when the factcheck node is done (also when Stage 4 is off or failed)
                            self._stage(rec, "report", "running", "Writing the report from the checked claims")
                    elif node == "report" and rec.stages["report"] == "running":
                        if not data:                                    # the node did nothing (skipped): the stage stays "not_run", the evidence report is all there is
                            self._stage(rec, "report", "not_run", message, data)
                        else:
                            self._stage(rec, "report", "failed" if data.get("status") == "failed" else "completed", message, data)
            self._complete(rec, usage_before)
        except Exception as e:
            logger.error("run %s failed:\n%s", rec.id, traceback.format_exc())
            running = [s for s, v in rec.stages.items() if v == "running"]
            if running == ["report"]:                                   # Stage 5 must never fail the run: everything before it is stored and readable
                self._stage(rec, "report", "failed", f"The written report failed: {type(e).__name__}: {str(e)[:200]}")
                self._complete(rec, usage_before)
                return
            rec.status, rec.finished_at = "failed", _now()
            rec.error = f"{type(e).__name__}: {str(e)[:300]}"
            for s in running:
                rec.stages[s] = "failed"
            rec.emit("run_failed", stage=running[0] if running else None, status="failed", message=rec.error)
        finally:
            progress.unregister(rec.id)
