"""Scopus proxy endpoints for the TRACE model-server wrapper (the FastAPI app that serves /decompose and /judge).

Why it lives on the host: Scopus returns abstracts (COMPLETE view) only to an entitled network. The host sits on the
campus network, the dev machines do not, and the SCOPUS_API_KEY never has to leave the host.

Mount it in the wrapper's main.py (two lines, after `app = FastAPI()` and `check_key` are defined):

    from scopus_router import make_router
    app.include_router(make_router(check_key))

Needs: SCOPUS_API_KEY in the container's environment (the compose file already passes `.env`; comma-separated keys are
allowed, the first is used), optional SCOPUS_INSTTOKEN, and `scopus_router.py` copied into the image next to main.py.
Endpoints (all need the same x-api-key header as the other endpoints):

    POST /scopus/search   {"query": "<Scopus query>", "count": 25, "start": 0, "sort": "relevancy"}
                          -> {"total": int, "entries": [raw Scopus entries], "view": "COMPLETE"|"STANDARD", "quota": {...}}
    GET  /scopus/status   -> {"configured": bool, "complete_view": bool, "quota": {...}}  (costs one Scopus request)

The router is a thin proxy: it forwards the query, drops the empty-result marker and passes the quota headers on. Turning
entries into papers happens in the pipeline, so changing the mapping needs no redeploy here.
"""
import os

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

SCOPUS_SEARCH_URL = "https://api.elsevier.com/content/search/scopus"
QUOTA_HEADERS = ("x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset")


class ScopusSearchReq(BaseModel):
    query: str                                   # Scopus search syntax, built by the client
    count: int = Field(25, ge=1, le=25)          # COMPLETE view allows at most 25 per request
    start: int = Field(0, ge=0, le=4975)
    sort: str = "relevancy"


def _api_key() -> str:
    for name in ("SCOPUS_API_KEY", "SCOPUS_API_KEYS"):
        value = os.getenv(name, "").split(",")[0].strip()
        if value:
            return value
    return ""


def _quota(resp: httpx.Response) -> dict:
    return {h.removeprefix("x-ratelimit-"): resp.headers.get(h) for h in QUOTA_HEADERS}


def make_router(check_key, http_client: httpx.Client | None = None) -> APIRouter:
    router = APIRouter()
    http = http_client or httpx.Client(timeout=30)

    def call(params: dict) -> httpx.Response:
        key = _api_key()
        if not key:
            raise HTTPException(503, "SCOPUS_API_KEY is not set on the server")
        headers = {"X-ELS-APIKey": key, "Accept": "application/json"}
        if os.getenv("SCOPUS_INSTTOKEN"):
            headers["X-ELS-Insttoken"] = os.environ["SCOPUS_INSTTOKEN"]
        try:
            return http.get(SCOPUS_SEARCH_URL, params=params, headers=headers)
        except httpx.TimeoutException:
            raise HTTPException(504, "Scopus timed out")
        except httpx.HTTPError as e:
            raise HTTPException(502, f"Scopus unreachable: {e}")

    @router.post("/scopus/search")
    def scopus_search(req: ScopusSearchReq, x_api_key: str = Header(None)):
        check_key(x_api_key)
        params = {"query": req.query, "count": req.count, "start": req.start, "sort": req.sort, "view": "COMPLETE"}
        r = call(params)
        view = "COMPLETE"
        if r.status_code in (401, 403):
            # no entitlement for abstracts from this network: fall back to the basic view so the caller can tell
            params["view"] = view = "STANDARD"
            r = call(params)
        if r.status_code == 429:
            raise HTTPException(429, "Scopus rate limit", headers={"Retry-After": r.headers.get("retry-after", "5")})
        if r.status_code == 400:
            raise HTTPException(400, f"Scopus rejected the query: {r.text[:300]}")
        if r.status_code in (401, 403):
            raise HTTPException(502, f"Scopus refused the key: {r.headers.get('x-els-status', r.status_code)}")
        if r.status_code != 200:
            raise HTTPException(502, f"Scopus error {r.status_code}: {r.text[:200]}")

        results = r.json().get("search-results", {})
        entries = [e for e in results.get("entry", []) if isinstance(e, dict) and "error" not in e]   # drops "Result set was empty"
        try:
            total = int(results.get("opensearch:totalResults", 0))
        except (TypeError, ValueError):
            total = 0
        return {"total": total, "entries": entries, "view": view, "quota": _quota(r)}

    @router.get("/scopus/status")
    def scopus_status(x_api_key: str = Header(None)):
        check_key(x_api_key)
        if not _api_key():
            return {"configured": False, "complete_view": False, "quota": {}}
        r = call({"query": "TITLE-ABS-KEY(speculative decoding)", "count": 1, "view": "COMPLETE"})
        return {"configured": True, "complete_view": r.status_code == 200, "http_status": r.status_code, "quota": _quota(r)}

    return router
