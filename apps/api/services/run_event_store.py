"""The timeline of a run, kept in the database (table run_events, migration 017).

A run's progress is a list of events (run_started, stage_started, step, ..., run_completed) that the run page draws as its timeline. They used to
live only in the memory of the API process, so a restart lost the timeline of every finished run. Now:

  write  RunRecord.emit hands every event to RunEventStore.append(). It only puts the event in a queue; a background thread writes the queue to
         the table in small batches (about once a second, at once when the run ends, and when the server shuts down). A slow or broken database
         can never slow down or fail a run: write errors are logged and the batch is dropped. A missing table (migration 017 not applied yet)
         gives one warning a minute.
  read   get_events(run_id) gives the stored events of a run in the shape of the stream; replay() turns them into what GET .../events sends for a
         run that is no longer in memory; get_run_times() gives the start, the end and the error of a stored run for GET .../research/{id}.

No LLM call. Reads raise connection errors (httpx.TransportError) so that the route's retry answers 503 and never "not found"; every other read
error means "no stored timeline", so the route falls back to its old behaviour (one closing event).
"""
import json
import logging
import math
import queue
import threading
import time
from typing import Optional

import httpx

from apps.api.services.db_service import _table_missing, strip_nul, supabase

logger = logging.getLogger("apps.api.run_event_store")

TABLE = "run_events"
TERMINAL = ("run_completed", "run_failed")
BATCH_SIZE = 50                     # rows per write
FLUSH_SECONDS = 1.0                 # the writer wakes at least this often
WRITE_ATTEMPTS = 3
WRITE_DELAYS = (0.5, 1.5)           # seconds before attempt 2 and 3
MISSING_TABLE_PAUSE = 60.0          # after "table missing", do not try (or warn) again for this long
READ_PAGE = 1000                    # PostgREST returns at most 1000 rows per request
INTERRUPTED = "The run did not finish (the server restarted or the run was stopped)."


# ------------------------------------------------------------------------------------------------------------------------------- rows
def _clean(value):
    """The value as JSON that Postgres accepts: NaN and infinity become null (jsonb has no such numbers), unknown types become text."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_clean(v) for v in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    return str(value)


def to_row(run_id: str, event: dict) -> dict:
    """One event of the stream as a row of run_events."""
    return strip_nul({"query_id": str(run_id), "seq": int(event["seq"]), "event": str(event["event"]), "stage": event.get("stage"),
                      "status": event.get("status"), "message": event.get("message") or "", "data": _clean(event.get("data") or {}),
                      "event_at": event.get("timestamp")})


def from_row(row: dict) -> dict:
    """One row of run_events as an event of the stream (the same keys and values the live stream sends)."""
    data = row.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError:
            data = {}
    return {"seq": row["seq"], "event": row["event"], "stage": row.get("stage"), "status": row.get("status"), "message": row.get("message") or "",
            "data": data if isinstance(data, dict) else {}, "timestamp": row.get("event_at")}


# ------------------------------------------------------------------------------------------------------------------------------ writer
class RunEventStore:
    """Writes the events of runs to the table from a background thread. `client` is a Supabase client; None means the one of db_service."""

    def __init__(self, client=None, batch_size: int = BATCH_SIZE, flush_seconds: float = FLUSH_SECONDS):
        self._client = client
        self._batch_size, self._flush_seconds = batch_size, flush_seconds
        self._queue: "queue.Queue[tuple[str, dict]]" = queue.Queue()
        self._wake = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._thread_lock = threading.Lock()
        self._stopping = False
        self._paused_until = 0.0
        self.written = 0                    # rows written (for tests and the logs)
        self.dropped = 0                    # rows given up on after a write failed

    # ---- called from the run's threads
    def append(self, run_id: str, event: dict) -> None:
        """Queue one event. Never blocks on the database and never raises."""
        try:
            self._ensure_thread()
            self._queue.put((str(run_id), event))
            if event.get("event") in TERMINAL or self._queue.qsize() >= self._batch_size:
                self._wake.set()
        except Exception:
            logger.debug("run event not queued", exc_info=True)

    def flush(self, timeout: float = 10.0) -> bool:
        """Wait until everything queued so far is written (or given up on). True when the queue is empty."""
        deadline = time.monotonic() + timeout
        self._wake.set()
        while self._queue.unfinished_tasks and time.monotonic() < deadline:
            time.sleep(0.02)
            self._wake.set()
        return self._queue.unfinished_tasks == 0

    def close(self, timeout: float = 5.0) -> None:
        """Write what is queued, then stop the thread (server shutdown)."""
        self.flush(timeout)
        self._stopping = True
        self._wake.set()

    # ---- the writer thread
    def _ensure_thread(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        with self._thread_lock:
            if self._thread is None or not self._thread.is_alive():
                self._stopping = False
                self._thread = threading.Thread(target=self._loop, name="run-event-writer", daemon=True)
                self._thread.start()

    def _loop(self) -> None:
        while not self._stopping:
            self._wake.wait(self._flush_seconds)
            self._wake.clear()
            try:
                self._drain()
            except Exception:                                   # nothing may kill the writer
                logger.exception("run event writer error")

    def _drain(self) -> None:
        items: list[tuple[str, dict]] = []
        while True:
            try:
                items.append(self._queue.get_nowait())
            except queue.Empty:
                break
        if not items:
            return
        try:
            rows = []
            for run_id, event in items:
                try:
                    rows.append(to_row(run_id, event))
                except Exception:                               # one malformed event must not lose the others
                    logger.warning("run event not stored (malformed): %r", str(event)[:120])
                    self.dropped += 1
            for i in range(0, len(rows), self._batch_size):
                self._write(rows[i:i + self._batch_size])
        finally:
            for _ in items:
                self._queue.task_done()

    def _write(self, rows: list[dict]) -> None:
        if time.monotonic() < self._paused_until:
            self.dropped += len(rows)
            return
        client = self._client or supabase
        for attempt in range(1, WRITE_ATTEMPTS + 1):
            try:
                client.table(TABLE).upsert(rows, on_conflict="query_id,seq").execute()
                self.written += len(rows)
                return
            except httpx.TransportError as e:
                logger.warning("run events: database connection error (attempt %d/%d): %s: %s", attempt, WRITE_ATTEMPTS, type(e).__name__, str(e)[:120])
                if attempt < WRITE_ATTEMPTS:
                    time.sleep(WRITE_DELAYS[min(attempt - 1, len(WRITE_DELAYS) - 1)])
            except Exception as e:
                if _table_missing(e, TABLE):
                    logger.warning("table %s is missing - run db/migrations/017_add_run_events.sql; the timeline of this run is not stored", TABLE)
                    self._paused_until = time.monotonic() + MISSING_TABLE_PAUSE
                else:
                    logger.warning("run events not stored: %s: %s", type(e).__name__, str(e)[:200])
                break
        self.dropped += len(rows)


# ------------------------------------------------------------------------------------------------------------------------------- reads
def get_events(query_id: str) -> list[dict]:
    """All stored events of a run, oldest first, in the shape of the stream. [] when the run has none (it ran before migration 017) or the table
    does not exist yet. A connection error is raised (the route retries it and answers 503)."""
    out: list[dict] = []
    start = 0
    while True:
        try:
            rows = (supabase.table(TABLE).select("seq,event,stage,status,message,data,event_at").eq("query_id", query_id)
                    .order("seq").range(start, start + READ_PAGE - 1).execute().data)
        except httpx.TransportError:
            raise
        except Exception as e:
            if _table_missing(e, TABLE):
                logger.warning("table %s is missing - run db/migrations/017_add_run_events.sql; no timeline can be read", TABLE)
            else:
                logger.warning("run events not read for %s: %s: %s", query_id, type(e).__name__, str(e)[:200])
            return []
        out += [from_row(r) for r in rows]
        if len(rows) < READ_PAGE:
            return out
        start += READ_PAGE


def get_run_times(query_id: str) -> dict:
    """{"startedAt", "finishedAt", "error"} of a stored run from its run_started and terminal events; {} when there are none. Connection errors are raised."""
    try:
        rows = (supabase.table(TABLE).select("seq,event,message,event_at").eq("query_id", query_id)
                .in_("event", ["run_started", *TERMINAL]).order("seq").execute().data)
    except httpx.TransportError:
        raise
    except Exception as e:
        if not _table_missing(e, TABLE):
            logger.warning("run times not read for %s: %s: %s", query_id, type(e).__name__, str(e)[:200])
        return {}
    out: dict = {}
    for r in rows:
        if r["event"] == "run_started":
            out["startedAt"] = r.get("event_at")
        else:
            out["finishedAt"] = r.get("event_at")
            if r["event"] == "run_failed":
                out["error"] = r.get("message") or None
    return out


def replay(stored: list[dict], next_index: int, status: Optional[str], error: Optional[str], report_url: str) -> list[dict]:
    """The events to send to a client that asks for a run that is not in memory: the stored events from `next_index` on (the client's resume point).
    A run that was cut off (the server stopped while it ran) has no closing event; one is added so that the client closes its stream: run_completed
    when `status` (the run's status from the database) says completed, otherwise run_failed, naming the stage that was running. When there is
    nothing after `next_index`, the closing event is sent again (the client keeps events by seq, so a duplicate counts once). `stored` must not be empty."""
    events = sorted(stored, key=lambda e: e["seq"])
    last = events[-1]
    if last["event"] not in TERMINAL:
        ok = status == "completed"
        running = [s for s in dict.fromkeys(e["stage"] for e in events if e["event"] == "stage_started" and e["stage"])
                   if not any(e["event"] == "stage_completed" and e["stage"] == s for e in events)]
        events.append({"seq": last["seq"] + 1, "event": "run_completed" if ok else "run_failed", "stage": None if ok else (running[0] if running else None),
                       "status": "completed" if ok else "failed", "message": "Run finished" if ok else (error or INTERRUPTED),
                       "data": {"reportUrl": report_url} if ok else {}, "timestamp": last["timestamp"]})
    after = [e for e in events if e["seq"] >= next_index]
    return after or [events[-1]]
