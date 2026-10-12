# Adding Scopus to the model-server wrapper (host machine)

1. Copy `scopus_router.py` next to the wrapper's `main.py` (the folder the compose `build: .` uses). If the Dockerfile copies
   files one by one, add `COPY scopus_router.py .`.
2. In `main.py`, after `app = FastAPI()` and the `check_key` function, add:

   ```python
   from scopus_router import make_router
   app.include_router(make_router(check_key))
   ```

3. Put the key in the host's `.env` (the compose file already passes it to the `query-generator` container via `env_file`):

   ```
   SCOPUS_API_KEY=<your key>
   ```

4. Rebuild and restart only the wrapper (vLLM does not need to restart):

   ```
   docker compose up -d --build query-generator
   ```

5. Check it from any machine on the Tailscale network:

   ```
   curl -s -H "x-api-key: <API_KEY>" https://mllab.tail0f44aa.ts.net/scopus/status
   ```

   Expected: `{"configured": true, "complete_view": true, "http_status": 200, "quota": {...}}`.
   `complete_view: false` means the host's network is not entitled to abstracts; `configured: false` means the key is missing.

The pipeline calls `POST /scopus/search`. If the endpoint is missing (404) or the host is unreachable, the pipeline logs one
warning and carries on without Scopus. The container reaches Scopus through the host's internet connection, so it uses the
campus IP.
