"""GET /api/research/{id}/report : the evidence report of a run (see services/report_service.py for what it contains and what it does not)."""
from fastapi import APIRouter, Depends, HTTPException

from apps.api.dependencies import get_run_manager
from apps.api.services import report_service
from apps.api.services.run_manager import RunManager

router = APIRouter(prefix="/api/research", tags=["report"])


@router.get("/{research_id}/report")
def get_report(research_id: str, manager: RunManager = Depends(get_run_manager)):
    rec = manager.get(research_id)
    if rec is not None and not rec.finished:
        raise HTTPException(status_code=409, detail="The run is not finished yet; follow /events and read the report after run_completed")
    try:
        report = report_service.build_report(research_id)
    except Exception:                                   # a malformed id, or the database rejecting the lookup
        report = None
    if report is None:
        raise HTTPException(status_code=404, detail="Research session not found")
    if rec is not None and rec.status == "failed":
        report["runError"] = rec.error                  # a failed run may still have stored a partial report; say so
    return report
