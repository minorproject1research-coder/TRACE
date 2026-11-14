# query_generator: API wrapper for the vLLM server

One FastAPI wrapper in front of one vLLM server. The vLLM server hosts two model names:
`judge` (base Qwen3.5-9B) and `planner` (your LoRA adapter on the same base weights).
All endpoints need the header `x-api-key`.

## Endpoints

| Endpoint | Model | Purpose |
|---|---|---|
| `POST /decompose` | planner | Break a research question into sub-questions and search queries |
| `POST /judge` | judge | Is a paper (title + abstract) relevant to a sub-question? |
| `POST /verify_evidence` | judge | Evidence judge for one finding (see below) |
| `POST /verify_evidence_batch` | judge | Evidence judge for many findings in one call (see below) |
| `GET /status` | - | vLLM up/down and the model names it serves |
| `DELETE /model` | - | Kept for old clients; does nothing (stop the container to free the GPU) |

## Evidence judge

Decides whether a finding is supported by its quote and whether it answers a research aspect.
It uses the same base judge model, temperature 0, and the existing vLLM connection.

### `POST /verify_evidence`

Request:
```json
{"aspect": "str", "claim": "str", "quote": "str", "context": "", "max_new_tokens": 200, "thinking": false}
```
Response:
```json
{"verdict": {"quote_supports_claim": "yes|partial|no",
             "answers_aspect": "yes|partial|no",
             "final": "yes|partial|no",
             "reason": "str"} | null,
 "raw_output": "str"}
```

- `final` is computed in code, not by the model: `yes` only if both answers are `yes`; `no` if either is `no`; otherwise `partial`.
- `verdict` is `null` when the reply cannot be parsed or an answer is not exactly yes/partial/no. `raw_output` is always returned.
- The model sometimes leaves out the final `}` of its JSON. A reply that is complete except for that one brace is accepted; a reply that is cut off mid-sentence is not (`verdict` is `null`).
- If vLLM is unreachable or returns an error, the call fails with HTTP 502.

### `POST /verify_evidence_batch`

Request:
```json
{"items": [{"id": "str", "aspect": "str", "claim": "str", "quote": "str", "context": ""}],
 "max_new_tokens": 200, "thinking": false}
```
Response:
```json
{"results": [{"id": "str", "verdict": {...same as above...} | null, "raw_output": "str", "error": "str | null"}]}
```

- Results come back in the same order and with the same ids as `items`.
- One failing item does not fail the batch: that item gets `verdict: null` and an `error` string.
- More than `MAX_VERIFY_ITEMS` items is rejected with HTTP 422.
- Items run concurrently (up to `MAX_VERIFY_CONCURRENCY`); vLLM does the actual batching.

### Example

```bash
curl -s -X POST http://localhost:8000/verify_evidence \
  -H "x-api-key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"aspect":"advantages of LoRA fine-tuning",
       "claim":"LoRA introduces no additional inference latency because the adapted weight can be merged back into the original matrix.",
       "quote":"LoRA and its related variants do not introduce any extra latency during the inference compared to the original model."}'
```

## Settings (environment variables, all optional)

| Variable | Default | Meaning |
|---|---|---|
| `MAX_VERIFY_ITEMS` | 64 | Largest allowed batch |
| `MAX_VERIFY_CONCURRENCY` | 8 | Parallel requests per batch |
| `MAX_FIELD_CHARS` | 1200 | `aspect`, `claim` and `quote` are cut to this before the prompt is built |
| `MAX_CONTEXT_CHARS` | 1500 | `context` is cut to this |

## Rebuild and restart the wrapper

vLLM does not need a restart.

```bash
docker compose up -d --build query-generator
```

## Tests

```bash
pip install pytest fastapi httpx pydantic        # once
pytest tests/test_verify_endpoints.py -v         # mocked vLLM, no GPU needed
API_KEY=your-key bash tests/smoke_verify_evidence.sh   # three real calls against the running server
```
