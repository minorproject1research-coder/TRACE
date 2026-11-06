"""API settings, all from the environment (see .env.example, section "API server")."""
import os


def _int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def cors_origins() -> list[str]:
    """Origins the browser frontend is served from (comma separated). Default: the Next.js dev server."""
    raw = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


# A run takes 15-25 minutes and uses the model server, Groq and the parsers, so runs are queued: MAX_CONCURRENT_RUNS at a time (default 1).
MAX_CONCURRENT_RUNS = _int("MAX_CONCURRENT_RUNS", 1)
MAX_PENDING_RUNS = _int("MAX_PENDING_RUNS", 5, minimum=0)         # queued runs beyond the running ones; more get HTTP 429
MAX_RUNS_IN_MEMORY = _int("MAX_RUNS_IN_MEMORY", 200)               # finished runs older than this are forgotten (their report stays in the database)

QUESTION_MIN_CHARS = 10
QUESTION_MAX_CHARS = 1000
