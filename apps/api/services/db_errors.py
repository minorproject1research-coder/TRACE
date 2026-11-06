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
