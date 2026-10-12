# Report 3 - Docling parsing speed: question, experiments, OCR finding, fix, decision

Date: 2026-10-11. Related: `01_markdown_parser_report.md` (what is done with Docling's output) and
`02_pipeline_runs_report.md` (run history).

Files: `scripts/bench_parsers.py` (new), `infra/docker-compose.bench.yml` (new),
`apps/api/agents/stage2_retrieval/paper_retrieval_agent.py` (`_parse_with_docling`), `infra/docker-compose.yml`,
`.env.example`, `.omo/PROJECT_ARCHITECTURE.md`.

## 1. The question

Paper parsing was the biggest cost of a pipeline run (about 5.5 of 12.5 minutes in run 3, even after parsing only the top
5 papers per sub-question). The proposal: **run the same Docling container two or more times on the parsing host, on
different ports, and spread the papers across them**, since that host has more CPU cores and RAM. Would that cut parsing time?

## 2. Test setup

- **Machine**: dev laptop, Intel Core Ultra 7 155H (16 cores, 22 threads), 15.5 GB RAM, Docker Desktop with 22 CPUs and
  7.5 GB for the Docker VM. **The real parsing host was not measured.**
- **Images** (neither was on the machine, both pulled): `ghcr.io/docling-project/docling-serve-cpu:latest` (7.53 GB,
  Docling 2.132.0) and `lakshyavarshney11/figure-extractor:latest` (2.05 GB, PDFFigures).
- **Container defaults found**: `DOCLING_SERVE_ENG_LOC_NUM_WORKERS=2`, `OMP_NUM_THREADS=4`,
  `DOCLING_SERVE_MAX_SYNC_WAIT=120` (a synchronous request waiting longer answers HTTP 504).
- **Workload**: 9 arXiv PDFs (187 KB to 2 MB), downloaded once and cached so downloads are not timed. Requests at
  increasing concurrency, spread round-robin when there are several containers, after a warm-up request.
- **Tools**: `scripts/bench_parsers.py` (`--docling`, `--figures`, `--concurrency`, `--options`) and
  `infra/docker-compose.bench.yml` (up to three Docling instances on ports 5101 to 5103 plus PDFFigures on 5002, under a
  separate project name so the real stack is untouched).

## 3. Experiments

| # | Experiment | Why |
|---|---|---|
| 1 | One Docling container at 1, 3, 6 concurrent requests | does one container already handle parallel requests? |
| 2 | Two and three containers, round-robin | the proposal itself |
| 3 | One container with 1, 2, 4 internal workers and 4 or 8 OMP threads | is a setting inside the container the limit? |
| 4 | One container with different conversion options (OCR, images, table mode, table structure) | why is one conversion so slow? |
| 5 | One container at 1, 4, 8 concurrent requests with OCR off | does concurrency work once the slow step is gone? |
| 6 | PDFFigures at 1, 3, 6 concurrent requests | is the second parsing service a bottleneck? |

## 4. Results

### 4.1 One Docling container (defaults, OCR on - how the pipeline ran)

| Concurrent requests | Wall time | Per-request min / median / max | Papers per minute |
|---|---|---|---|
| 1 | 12 to 14 s | 12 to 14 s | 4.3 to 5.0 |
| 3 | 44.1 s | 18 / 24 / 44 s | 4.1 |
| 6 | 120.2 s | 8 / 32 / 78 s, **5 of 6 ok, one HTTP 504** | 2.5 |

Three requests at once took as long as three in a row: the container effectively serves one conversion at a time. The
504 is the 120 s synchronous wait limit.

### 4.2 More Docling containers (OCR on) - **slower, not faster**

| Containers | Concurrency | Wall time | Papers per minute | Notes |
|---|---|---|---|---|
| 2 | 2 / 4 / 6 | 36 / 106 / 120 s | 3.3 / 2.3 / 2.5 | one 504 at 6 |
| 3 | 3 / 6 / 9 | 44 / 121 / 121 s | 4.1 / 1.5 / 1.5 | 3 of 6 and 3 of 9 ok; connection errors, 504s |

One container showed **1753% CPU** (about 17.5 of the 22 threads) during the run, so extra containers only compete for the
same cores. The three containers together also hit the Docker memory limit (they were later found with exit code 137,
an out-of-memory kill; each uses about 2 to 3 GB).

### 4.3 Settings inside one container (OCR on, sync wait raised to 900 s)

| Workers | OMP threads | 4 concurrent | 8 concurrent |
|---|---|---|---|
| 1 | 4 | 2.0 papers/min | 2.0 |
| 2 (default) | 4 | 2.1 | 2.3 |
| 4 | 4 | 2.2 | 2.2 |
| 4 | 8 | 2.1 | 1.9 |

Neither setting changed anything; single-request latency stayed at 12 s in every case.

### 4.4 PDFFigures
1 request 3 s; 3 concurrent 12.7 s; 6 concurrent 23.2 s (15 to 20 papers per minute). It also serves one request at a
time but is about four times faster than Docling, so it is not the bottleneck.

## 5. The finding: every paper was converted with OCR

Reading the server's OpenAPI schema showed that conversion options live in an `options` object (`to_formats`, `do_ocr`,
`do_table_structure`, `table_mode`, `include_images`, ...). The pipeline sent `"output_formats": ["markdown"]` at the top
level, which the server ignores, so **every conversion ran with the defaults: OCR on, accurate table mode, picture images
generated at 2x scale.**

Same 5 papers, one request at a time:

| Options | Median per paper | Total | Markdown characters | Table rows |
|---|---|---|---|---|
| defaults (what the pipeline sent) | 24.2 s | 158.5 s | 278,696 | 100 |
| `do_ocr=false` | 10.1 s | **70.5 s** | 278,662 | 100 |
| + `include_images=false` | 10.1 s | 68.6 s | 278,662 | 100 |
| + `table_mode=fast` | 10.1 s | 64.5 s | 275,912 | 104 |
| + `do_table_structure=false` | 10.1 s | 62.6 s | 263,812 | **22** |

- **OCR off is 2.2 times faster with essentially the same text** (34 characters of 278,696 differ). OCR only matters for
  scanned pages; these PDFs have a text layer.
- **Table recognition stays on**: switching it off loses most tables (22 rows instead of 100). Fast table mode saves only
  about 6% and was not adopted.
- **With OCR off, concurrency stops hurting** (one container, 2 workers): 1 request 5.0 papers/min, 4 concurrent 4.8,
  8 concurrent 5.4 (with OCR on it fell to about 2). On this machine it is still CPU-bound at about 5 papers/min.

## 6. The fix that was made

In `_parse_with_docling`:
- Requests use the documented field: `options: {"to_formats": ["md"], "do_ocr": false, "include_images": false}`; table
  recognition stays on. `DOCLING_DO_OCR=true` forces OCR back on.
- **Scanned PDFs are still handled**: a result under 500 characters without OCR is retried once with OCR on. Tested with an
  image-only page: the retry fired and recovered the text (633 characters). A normal paper parsed correctly through the
  same code path (24 sections, 29 references).
- Request timeout is configurable (`DOCLING_TIMEOUT_SECONDS`, default 300 s).
- `infra/docker-compose.yml` sets `DOCLING_SERVE_MAX_SYNC_WAIT=600` on the Docling service (the default 120 s caused the
  504s when requests queued). **This needs redeploying on the host.**
- The findings are recorded in `.omo/PROJECT_ARCHITECTURE.md`; `.env.example` has the two new variables.

## 7. Decision

| Question | Decision | Reason |
|---|---|---|
| Run several Docling containers on the dev machine? | **No** | measured slower, and it exhausts memory |
| Run several Docling containers on the parsing host? | **No (measured, section 10)** | 1, 2 and 4 containers all gave about 10 papers/min on the 32-core host |
| Keep OCR on? | **No: off by default, automatic OCR retry for scanned PDFs** | 2.2x faster, same text |
| Keep table recognition on? | **Yes** | switching it off loses most tables |
| Change worker or thread settings? | **No** | no effect in the tests |

## 8. What is not known

- **The parsing host was not measured**, only the laptop; absolute speed (about 5 papers/min) will differ there.
- The sample was small (5 to 9 mostly short arXiv papers). Long, figure-heavy or scanned papers take longer, and the
  scanned-PDF retry brings back the OCR cost for those.
- Single-request latency varied between series (12 to 24 s with the default settings, depending on which PDFs were in the
  series), so only same-series comparisons are meaningful; the 2.2x ratio comes from one series.
- **No full pipeline run has been done with the fix**, so the effect on the "Parsing done" time (5m 36s in run 3) is not
  confirmed. That time also includes downloads, DOI landing-page failures and Playwright fallbacks, which this change does
  not touch.

## 9. Next actions

1. Redeploy the Docling container on the host with the updated compose file (new `MAX_SYNC_WAIT`).
2. Run on the host: `bash scripts/bench_host.sh`. It starts 1, 2 and then 4 Docling containers (each limited to an equal share
   of the cores, ports 5201 and up, OCR off), prints papers per minute at several concurrency levels, and removes them.
   More containers are worth deploying only if papers/min rises clearly with N (a host with many more cores may leave cores
   idle in one container).
3. Run the full pipeline and compare the parsing time with run 3.
4. Continue with the parsing-related backlog: prefer papers with a direct PDF link; Stage 3 choosing papers with usable text.

## 10. Host benchmark (2026-10-12, `scripts/bench_host.sh`, OCR off)

Host: 32 cores, about 31 GB free memory. Each row is one run of the same PDFs; `c` is the number of simultaneous requests.

| Containers (cores each) | c | Wall time | Per-request min / median / max | Papers per minute |
|---|---|---|---|---|
| 1 (32) | 1 | 6.0 s | 6 / 6 / 6 | 10.0 |
| 1 (32) | 2 | 8.0 s | 8 / 8 / 8 | 14.9 |
| 1 (32) | 4 | 24.1 s | 6 / 11 / 24 | 10.0 |
| 2 (16) | 1 | 6.0 s | 6 / 6 / 6 | 9.9 |
| 2 (16) | 2 | 10.1 s | 8 / 9 / 10 | 11.9 |
| 2 (16) | 4 | 24.3 s | 8 / 14 / 24 | 9.9 |
| 2 (16) | 8 | 46.1 s | 6 / 22 / 46 | 10.4 |
| 4 (8) | 1 | 8.0 s | 8 / 8 / 8 | 7.5 |
| 4 (8) | 4 | 24.1 s | 10 / 14 / 24 | 10.0 |
| 4 (8) | 8 | 44.2 s | 14 / 25 / 44 | 10.9 |
| 4 (8) | 16 | 90.2 s | 10 / 44 / 90 | 10.6 |

All 8 to 16 requests per level succeeded (no errors, no timeouts).

Findings:
- **More containers do not raise throughput**: about 10 to 11 papers/min for 1, 2 and 4 containers alike (the single 14.9 is a two-request burst, probably noise).
- **The host is about twice as fast per paper as the laptop** (6 s against 10 to 12 s; about 10 against about 5 papers/min).
- **A conversion hardly depends on core count**: 6 s on 32 cores, 6 s on 16, 8 s on 8. So a single conversion is not core-bound.
- **Yet wall time is almost exactly 6 s x the number of requests** (4 -> 24 s, 8 -> 44 to 46 s, 16 -> 90 s) for any number of containers. Independent containers would finish 4 requests on 4 containers in about 8 s, not 24 s, so something shared and serial limits throughput. The data cannot say what: candidates are the benchmark client (one Python process on the host), a shared host resource, or other load on the host (the vLLM server runs there). Not resolved.
- **The pipeline's own conversions took 27 to 37 s per paper** with 3 at once (run 4), against 6 s here, so Docling compute is not what makes the pipeline's parsing slow. Likely causes (not yet measured): sending each PDF from the dev machine to the host over Tailscale, PDFFigures running in parallel, and download failures with their fallbacks.

Decision: keep a single Docling container; do not deploy more.

To separate the open questions (each is one command):
1. Client or host? Run two copies of the benchmark client at once against two containers; if throughput doubles, the single client was the limit.
2. Upload cost: `python scripts/bench_parsers.py --docling http://<host>:5001 --figures http://<host>:5002 --concurrency 1,3 --options '{"do_ocr": false, "include_images": false}'` from the dev machine (over Tailscale), compared with the 6 s above.
3. OCR on the host: the same benchmark on the host with `--options '{"do_ocr": true}'`, to confirm the 2.2x seen on the laptop.
