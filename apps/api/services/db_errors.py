"""Database read helpers for the API routes.

The Supabase client sometimes drops a keep-alive connection ("httpx.RemoteProtocolError: Server disconnected"), most often when several
requests arrive together. The routes used to turn that into a wrong answer (a 500 for a session, a 404 "not found" for an existing report).
Now an idempotent read is retried once on a connection error and, if it still fails, answered with 503, never with 404.
"""
import logging
import time
import uuid
from typing import Callable, TypeVar

import httpx

logger = logging.getLogger("apps.api.db")
T = TypeVar("T")

RETRY_DELAY_SECONDS = 0.3


class DatabaseUnavailable(Exception):
    """The database could not be reached (after one retry)."""


def valid_uuid(value: str) -> bool:
    """Research and paper ids are UUIDs; anything else cannot exist, so the route answers 404 without asking the database."""
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def read_with_retry(fn: Callable[..., T], *args, **kwargs) -> T:
    """Call a read-only function; retry once on a connection error; raise DatabaseUnavailable if it fails again.
    Only for idempotent reads: never wrap a write in this."""
    for attempt in (1, 2):
        try:
            return fn(*args, **kwargs)
        except httpx.TransportError as e:                       # includes RemoteProtocolError, ReadTimeout, ConnectError
            logger.warning("database read failed (attempt %d/2): %s: %s", attempt, type(e).__name__, str(e)[:120])
            if attempt == 2:
                raise DatabaseUnavailable(f"{type(e).__name__}") from e
            time.sleep(RETRY_DELAY_SECONDS)
    raise AssertionError("unreachable")


# ---------------------------------------------------------------------------------------------------------------------------------
# The pipeline's own database calls (planned item B8). Four on-topic papers were lost in three runs because one dropped connection
# ("Server disconnected", "EOF occurred in violation of protocol", "ConnectionTerminated") failed a paper read or store that would
# have worked a moment later. These calls fail with the original error after the last attempt, so the callers' handling is unchanged.
# ---------------------------------------------------------------------------------------------------------------------------------
import functools

TRANSIENT_ATTEMPTS = 3
TRANSIENT_DELAYS = (0.5, 1.5)             # seconds before attempt 2 and 3


def retry_transient(fn: Callable[..., T]) -> Callable[..., T]:
    """Decorator: call `fn`, and on a connection error (httpx.TransportError) try again up to TRANSIENT_ATTEMPTS times in all.
    Only for idempotent calls: reads, and writes that check for an existing row first. Any other error (a database error answer,
    a bug) is raised at once; the last connection error is raised as it was."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        for attempt in range(1, TRANSIENT_ATTEMPTS + 1):
            try:
                return fn(*args, **kwargs)
            except httpx.TransportError as e:
                logger.warning("%s: database connection error (attempt %d/%d): %s: %s",
                               fn.__name__, attempt, TRANSIENT_ATTEMPTS, type(e).__name__, str(e)[:120])
                if attempt == TRANSIENT_ATTEMPTS:
                    raise
                time.sleep(TRANSIENT_DELAYS[min(attempt - 1, len(TRANSIENT_DELAYS) - 1)])
        raise AssertionError("unreachable")
    return wrapper
