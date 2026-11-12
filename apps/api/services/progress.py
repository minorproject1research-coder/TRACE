"""Progress reports from INSIDE a pipeline node, so the UI can show what a stage is doing between its start and its end.

A node calls   progress.report(query_id, "papers", "parsing", "running", "Parsed 3 of 10 papers", usable=3, target=10)
The run manager registers a sink for the run (the run id IS the query id) and turns each report into an event on the run's stream.

  lane   "papers" | "web"  (the two retrieval branches, which run at the same time)  |  "summarizer"  |  "factcheck"  |  "report"  (Stage 5: steps
         sections, write, validate, summary, references)
  step   "branch" (the lane started) or a step of the lane, e.g. "search", "relevance_filter", "scoring", "store", "parsing", "digest", "judge"
  state  "running" | "completed" | "skipped" | "failed"

No LLM call, no write. A report must never break a run: report() swallows every error. A lane with no registered sink (a test, a script
such as test_pipeline.py) simply reports nowhere.
"""
import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger("apps.api.progress")

LANES = ("papers", "web", "summarizer", "factcheck", "report", "notes")
STATES = ("running", "completed", "skipped", "failed")

Sink = Callable[[dict], None]
_sinks: dict[str, Sink] = {}
_lock = threading.Lock()


def register(run_id: str, sink: Sink) -> None:
    with _lock:
        _sinks[str(run_id)] = sink


def unregister(run_id: str) -> None:
    with _lock:
        _sinks.pop(str(run_id), None)


def report(run_id: Optional[str], lane: str, step: str, state: str = "running", message: str = "", **data) -> None:
    """Tell whoever follows run `run_id` that `step` of `lane` is now `state`. `data` holds small numbers (counts), never large payloads."""
    if not run_id:
        return
    try:
        with _lock:
            sink = _sinks.get(str(run_id))
        if sink is not None:
            sink({"lane": lane, "step": step, "state": state, "message": message, "data": data})
    except Exception:                       # a progress report must never break the pipeline
        logger.debug("progress report dropped", exc_info=True)


def note(run_id: Optional[str], code: str, message: str, level: str = "info", stage: Optional[str] = None, **data) -> None:
    """Something worth knowing about this run that is not a step: a cache that was used, a source that was skipped, failures of PDFs. The event is
    a step event of the lane "notes" (step = `code`, state "completed"); data has level ("info" | "warn"), stage ("planner" | "retrieval" |
    "summarizer" | "factcheck" | "report") and small counts. Never raises."""
    report(run_id, "notes", code, "completed", message, level=level, stage=stage, **data)
