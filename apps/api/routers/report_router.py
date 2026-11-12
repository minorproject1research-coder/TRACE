"""The reports of a run.

  GET  /api/research/{id}/report           the EVIDENCE report (see services/report_service.py for what it contains and what it does not)
  GET  /api/research/{id}/written-report   the WRITTEN report of Stage 5 (docs/STAGE5_OUTPUT.md): 200 {status, report, markdown, stats, model,
                                           templateVersion, generatedAt}; 202 {"state": "running"} while it is being written; 404 when there is none
  POST /api/research/{id}/written-report   write it again from the STORED run (only with STAGE5=true): 202 {"state": "started"}, 409 when one is
                                           already running for this id (or the run is not finished), 400 when STAGE5 is off
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from apps.api.dependencies import get_run_manager
from apps.api.services import db_service, report_service
from apps.api.services.db_errors import read_with_retry, valid_uuid
from apps.api.services.run_manager import RunManager

router = APIRouter(prefix="/api/research", tags=["report"])


@router.get("/{research_id}/report")
def get_report(research_id: str, manager: RunManager = Depends(get_run_manager)):
    rec = manager.get(research_id)
    if rec is not None and not rec.finished:
        raise HTTPException(status_code=409, detail="The run is not finished yet; follow /events and read the report after run_completed")
    # a database failure is a 503 (DatabaseUnavailable, handled in main.py), never a 404: the report may well exist
    report = read_with_retry(report_service.build_report, research_id) if valid_uuid(research_id) else None
    if report is None:
        raise HTTPException(status_code=404, detail="Research session not found")
    if rec is not None and rec.status == "failed":
        report["runError"] = rec.error                  # a failed run may still have stored a partial report; say so
    return report


@router.get("/{research_id}/written-report")
def get_written_report(research_id: str, manager: RunManager = Depends(get_run_manager)):
    rec = manager.get(research_id)
    live_writing = rec is not None and rec.stages.get("report") == "running"
    if live_writing or report_service.written_report_running(research_id):
        return JSONResponse(status_code=202, content={"state": "running"})          # poll again; it is 200 with the report when Stage 5 is done
    # a database failure is a 503 (DatabaseUnavailable, handled in main.py), never a 404: the report may well exist
    row = read_with_retry(db_service.get_written_report, research_id) if valid_uuid(research_id) else None
    if row is None:
        why = report_service.written_report_error(research_id)
        raise HTTPException(status_code=404, detail="No written report for this run (Stage 5 did not run, or it has not been stored)"
                            + (f"; the last attempt failed: {why}" if why else ""))
    return report_service.written_report_view(row)


@router.post("/{research_id}/written-report", status_code=202)
def write_report_again(research_id: str, manager: RunManager = Depends(get_run_manager)):
    from apps.api.agents.stage5_report import settings as stage5        # light: only reads the environment
    if not stage5.stage5_enabled():
        raise HTTPException(status_code=400, detail="Stage 5 is switched off: set STAGE5=true in the environment of the server and restart it")
    rec = manager.get(research_id)
    if rec is not None and not rec.finished:
        raise HTTPException(status_code=409, detail="The run is not finished yet; Stage 5 runs at its end")
    if rec is None and (not valid_uuid(research_id) or read_with_retry(report_service.session_from_db, research_id) is None):
        raise HTTPException(status_code=404, detail="Research session not found")
    if not report_service.start_written_report(research_id):
        raise HTTPException(status_code=409, detail="The written report of this run is already being written")
    return {"state": "started"}
