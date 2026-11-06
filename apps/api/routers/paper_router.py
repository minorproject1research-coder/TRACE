"""The papers and web sources of a run (read-only), for the Activity tab and the paper page.

  GET /api/research/{id}/papers              the retrieval funnel and a summary of every paper and web source kept so far (works while the run goes)
  GET /api/research/{id}/papers/{paper_id}   one paper: links, scores, abstract, parsed content with the findings' quotes located in it
"""
from fastapi import APIRouter, Depends, HTTPException

from apps.api.dependencies import get_run_manager
from apps.api.services import paper_service
from apps.api.services.db_errors import read_with_retry, valid_uuid
from apps.api.services.run_manager import RunManager

router = APIRouter(prefix="/api/research", tags=["papers"])

_EMPTY_COUNTS = {"papersKept": 0, "papersParsed": 0, "papersUsedAsEvidence": 0, "papersUsedFullText": 0, "papersUsedAbstractOnly": 0,
                 "papersWithPdfLink": 0, "webFound": 0, "webUsedAsEvidence": 0, "subQuestions": 0}


@router.get("/{research_id}/papers")
def list_papers(research_id: str, manager: RunManager = Depends(get_run_manager)):
    overview = read_with_retry(paper_service.build_papers_overview, research_id) if valid_uuid(research_id) else None
    if overview is None:
        if manager.get(research_id) is not None:      # queued: the planner has not written the query row yet
            return {"id": research_id, "counts": dict(_EMPTY_COUNTS), "subQuestions": [], "papers": [], "web": []}
        raise HTTPException(status_code=404, detail="Research session not found")
    return overview


@router.get("/{research_id}/papers/{paper_id}")
def get_paper(research_id: str, paper_id: str):
    detail = read_with_retry(paper_service.build_paper_detail, research_id, paper_id) if valid_uuid(research_id) else None
    if detail is None:
        raise HTTPException(status_code=404, detail="Paper not found in this research session")
    return detail
