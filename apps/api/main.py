"""TRACE API.   Run:  uvicorn apps.api.main:app --host 0.0.0.0 --port 8000      (from the repository root, with the .env in place)

  GET  /health                       liveness + number of active runs
  POST /api/research                 start a run                         (routers/query_router.py)
  GET  /api/research                 latest runs
  GET  /api/research/{id}            status
  GET  /api/research/{id}/events     live progress (server-sent events)
  GET  /api/research/{id}/report     the evidence report                (routers/report_router.py)
  GET  /api/research/{id}/papers     retrieval funnel + every paper / web source kept (routers/paper_router.py)
  GET  /api/research/{id}/papers/{paper_id}   one paper: links, scores, parsed content, quotes located in it

A run takes 15-25 minutes and is executed in a background thread; runs are queued (MAX_CONCURRENT_RUNS, default 1). The API writes the
same log files as test_pipeline.py (logs/pipeline.log and one file per stage), so scripts/pipeline_run_report.py works on API runs too.
There is no authentication yet: do not expose this port to the internet as it is.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

load_dotenv()

from apps.api import config  # noqa: E402  (after load_dotenv, so the settings see the .env)
from apps.api.dependencies import get_run_manager, shutdown_run_manager  # noqa: E402
from apps.api.routers import paper_router, query_router, report_router  # noqa: E402
from apps.api.services.db_errors import DatabaseUnavailable  # noqa: E402

STAGE_LOG_FILES = {
    "apps.api.agents.stage1_planner": "stage1_planner.log",
    "apps.api.agents.stage2_retrieval": "stage2_retrieval.log",
    "apps.api.agents.stage3_summarizer": "stage3_summarizer.log",
    "apps.api.agents.stage4_factcheck": "stage4_factcheck.log",
    "apps.api.agents.stage5_report": "stage5_report.log",
}


def configure_logging(log_dir: str = "logs") -> None:
    """The same files as test_pipeline.py: logs/pipeline.log (everything) and one file per stage, UTF-8. Safe to call twice."""
    root = logging.getLogger()
    if any(getattr(h, "_trace_pipeline_log", False) for h in root.handlers):
        return
    path = Path(log_dir)
    path.mkdir(exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    root.setLevel(logging.INFO)
    handlers = [logging.FileHandler(path / "pipeline.log", encoding="utf-8"), logging.StreamHandler()]
    for h in handlers:
        h.setFormatter(fmt)
        h._trace_pipeline_log = True
        root.addHandler(h)
    for logger_name, filename in STAGE_LOG_FILES.items():
        h = logging.FileHandler(path / filename, encoding="utf-8")
        h.setFormatter(fmt)
        logging.getLogger(logger_name).addHandler(h)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logging.getLogger("apps.api").info("TRACE API started (CORS origins: %s)", ", ".join(config.cors_origins()))
    yield
    shutdown_run_manager()


app = FastAPI(title="TRACE API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.cors_origins(), allow_methods=["GET", "POST", "OPTIONS"],
                   allow_headers=["*"], expose_headers=["Location"])
app.add_middleware(GZipMiddleware, minimum_size=1024)       # a parsed paper is up to a few hundred KB of text; text/event-stream is excluded by default
app.include_router(query_router.router)
app.include_router(report_router.router)
app.include_router(paper_router.router)


@app.exception_handler(DatabaseUnavailable)
async def database_unavailable(_: Request, __: DatabaseUnavailable):
    """A read that failed twice on a connection error: say so (503), do not pretend the run does not exist (404)."""
    return JSONResponse(status_code=503, content={"detail": "The database is temporarily unavailable. Try again in a moment."},
                        headers={"Retry-After": "2"})


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "activeRuns": get_run_manager().active_count()}
