"""Research sessions: start a run, read its status, follow its progress.

  POST /api/research               start a run (202); body {question}
  GET  /api/research               the latest runs (from the database)
  GET  /api/research/{id}          status of one run
  GET  /api/research/{id}/events   server-sent events: the progress of the run (replayed from the start, resumable with Last-Event-ID)
"""
import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from apps.api import config
from apps.api.dependencies import get_run_manager
from apps.api.services import report_service
from apps.api.services.db_errors import read_with_retry, valid_uuid
from apps.api.services.run_manager import QueueFull, RunManager, TERMINAL

router = APIRouter(prefix="/api/research", tags=["research"])


class ResearchRequest(BaseModel):
    question: str = Field(min_length=config.QUESTION_MIN_CHARS, max_length=config.QUESTION_MAX_CHARS)

    @field_validator("question")
    @classmethod
    def _tidy(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < config.QUESTION_MIN_CHARS:
            raise ValueError(f"the question must have at least {config.QUESTION_MIN_CHARS} characters")
        return value


def _sse(event: dict) -> str:
    return f"id: {event['seq']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"


_SSE_HEADERS = {"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}


@router.post("", status_code=202)
def create_research(body: ResearchRequest, response: Response, manager: RunManager = Depends(get_run_manager)):
    try:
        rec = manager.submit(body.question)
    except QueueFull as e:
        raise HTTPException(status_code=429, detail=str(e))
    response.headers["Location"] = f"/api/research/{rec.id}"
    return rec.session()


@router.get("")
def list_research(limit: int = Query(20, ge=1, le=100), manager: RunManager = Depends(get_run_manager)):
    """Runs from the database, newest first; a run that is live in this process shows its live status."""
    live = {r.id: r.session() for r in manager.recent(limit)}
    stored = [s for s in read_with_retry(report_service.list_sessions, limit) if s["id"] not in live]
    items = sorted([*live.values(), *stored], key=lambda s: s.get("createdAt") or "", reverse=True)[:limit]
    return {"items": [{k: s.get(k) for k in ("id", "question", "status", "createdAt")} for s in items]}


@router.get("/{research_id}")
def get_research(research_id: str, manager: RunManager = Depends(get_run_manager)):
    rec = manager.get(research_id)
    if rec is not None:
        return rec.session()
    session = read_with_retry(report_service.session_from_db, research_id) if valid_uuid(research_id) else None
    if session is None:
        raise HTTPException(status_code=404, detail="Research session not found")
    return session


@router.get("/{research_id}/events")
async def research_events(research_id: str, request: Request, after: Optional[int] = Query(None, ge=-1),
                          manager: RunManager = Depends(get_run_manager)):
    """Server-sent events (default 'message' type, so EventSource.onmessage receives them). Every event has a numeric id (seq). A client that
    reconnects sends Last-Event-ID (or ?after=<seq>) and continues from the next event. The stream ends after run_completed / run_failed:
    the client must close its EventSource when it sees one of them, or it will reconnect."""
    rec = manager.get(research_id)
    if rec is None:
        session = await asyncio.to_thread(read_with_retry, report_service.session_from_db, research_id) if valid_uuid(research_id) else None
        if session is None:
            raise HTTPException(status_code=404, detail="Research session not found")
        event = {"seq": 0, "event": "run_completed" if session["status"] == "completed" else "run_failed", "stage": None, "status": session["status"],
                 "message": session["error"] or "Run finished", "data": {"reportUrl": f"/api/research/{research_id}/report"}, "timestamp": None}

        async def one():
            yield _sse(event)
        return StreamingResponse(one(), media_type="text/event-stream", headers=_SSE_HEADERS)

    header = request.headers.get("last-event-id", "")
    next_index = (after + 1) if after is not None else (int(header) + 1 if header.isdigit() else 0)

    async def stream():
        index, idle = next_index, 0.0
        while True:
            if await request.is_disconnected():
                return
            batch = rec.events_from(index)
            for event in batch:
                yield _sse(event)
                index = event["seq"] + 1
                if event["event"] in TERMINAL:
                    return
            idle = 0.0 if batch else idle + 0.5
            if idle >= 15:
                yield ": keep-alive\n\n"
                idle = 0.0
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream", headers=_SSE_HEADERS)
