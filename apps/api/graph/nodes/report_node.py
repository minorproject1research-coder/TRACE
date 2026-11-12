"""Stage 5 as a graph node: writes the report from the verified claims of Stage 4 (what it may say, which citations and which gaps are decided by
Python; the model only phrases sentences; see docs/STAGE5.md and apps/api/agents/stage5_report/assembler.py).

  STAGE5=false     switch (default off: the node returns {} and the stage stays "not run")

The node runs only when Stage 4 ran (it has claims, an error, or a per-sub-question summary in the state): with FACTCHECK off there are no labels
to write from, so it returns {} and leaves a note. A Stage 5 failure never fails the run: the evidence of Stages 3 and 4 is already stored.
The result is saved with db_service.write_written_report (imported late and tolerated when missing or failing) and returned as the state fields
`written_report` (the structured report) and `written_report_status`.

Progress lane "report", steps: sections, write (one report per finished model call), validate, summary, references, store. Notes (code
stage5_skipped, stage5_fallback, stage5_dropped) go through progress.note with stage "report".
"""
import logging

from apps.api.agents.stage5_report import assembler, loader, settings
from apps.api.services import progress

logger = logging.getLogger("apps.api.agents.stage5_report")

LANE = "report"


def enabled() -> bool:
    return settings.stage5_enabled()


def _get(obj, key, default=None):
    """obj[key] for a dict, obj.key for an object (the graph state is a pydantic model; tests pass dicts or SimpleNamespace)."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _query_id(state) -> str:
    plan = _get(state, "task_plan")
    return str(_get(state, "query_id") or _get(plan, "query_id") or "")


def stage4_ran(state) -> bool:
    """Stage 4 ran when the state holds claims, a whole-stage error or a per-sub-question summary (it is empty when FACTCHECK is off)."""
    return bool(_get(state, "fact_claims") or _get(state, "fact_summary"))


def _small(data: dict) -> dict:
    """Progress data is small counts only: numbers and booleans (a section title or any text is dropped)."""
    return {k: v for k, v in data.items() if isinstance(v, (int, float, bool))}


def _progress_callback(qid: str):
    """Turns the assembler's progress(step, message, **data) into progress.report / progress.note; `data["state"]` is the lane state."""
    def callback(step, message="", **data):
        if step == "note":
            progress.note(qid, str(data.get("code") or "stage5_note"), message, level=str(data.get("level") or "info"), stage=LANE, **_small(data))
            return
        state = str(data.pop("state", "running"))
        progress.report(qid, LANE, step, state, message, **_small(data))
    return callback


def _persist(qid: str, result: dict) -> bool:
    """Saves the report; True when it was stored. The function is added by the persistence layer (db_service.write_written_report); a missing
    or failing one costs the stored copy, not the run."""
    try:
        from apps.api.services import db_service
        write = getattr(db_service, "write_written_report", None)
        if write is None:
            logger.warning("Stage 5 report not stored: db_service.write_written_report does not exist")
            return False
        write(qid, result["status"], result["report"], result["markdown"], result["stats"], result["model"], result["template_version"])
        return True
    except Exception as e:                                  # noqa: BLE001
        logger.warning("Stage 5 report not stored: %s: %s", type(e).__name__, str(e)[:200])
        return False


def report_node(state) -> dict:
    if not enabled():
        return {}
    qid = _query_id(state)
    try:
        if not stage4_ran(state):
            progress.note(qid, "stage5_skipped", "The written report was skipped because fact checking (Stage 4) did not run", level="info", stage=LANE)
            return {}
        progress.report(qid, LANE, "branch", "running", "Writing the report")
        try:
            inputs = loader.from_state(state)
        except Exception as e:                              # noqa: BLE001
            logger.exception("Stage 5 could not read its inputs")
            result = assembler.failed_result({"question": _get(state, "raw_query")}, e)
        else:
            result = assembler.build_report(inputs, progress=_progress_callback(qid))
        stored = _persist(qid, result)
        status = result["status"]
        counts = (result["report"].get("overview") or {}).get("counts") or {}
        progress.report(qid, LANE, "store", "failed" if status == "failed" else "completed",
                        f"Report {status.replace('_', ' ')}" + ("" if stored else " (not stored)"),
                        sections=counts.get("sections", 0), sentences=counts.get("sentences", 0), references=counts.get("references", 0),
                        warnings=len(result["warnings"]), stored=stored)
        return {"written_report": result["report"], "written_report_status": status}
    except Exception as e:                                  # noqa: BLE001  (a Stage 5 failure never fails the run)
        logger.exception("Stage 5 failed")
        try:
            progress.report(qid, LANE, "store", "failed", f"The written report failed: {type(e).__name__}")
        except Exception:                                   # noqa: BLE001
            pass
        return {"written_report": {"status": "failed", "warnings": [f"{type(e).__name__}: {str(e)[:200]}"]}, "written_report_status": "failed"}
