# Report 5 - PDF downloads that fail (all runs in the log)

Date: 2026-10-12. Source: `logs/pipeline.log` (11 log segments from 2026-09-20 to 2026-10-12), matched to the papers in Supabase, plus an
open-access check against OpenAlex and Unpaywall and a test of three possible fixes. Files: `failed_pdf_downloads.csv` / `.json` (the list),
`failed_pdf_fix_feasibility.json` (the test result per paper). The tests ran from the dev laptop, not from the campus host.

## 1. Summary

- **40 "All PDF URLs failed" events in the log = 24 different papers.** 16 of the events were the same paper failing again in a later
  run (10 papers failed more than once; the worst four times). Not one of them was ever parsed successfully from another row.
- Every failure ends the same way: the pipeline has already tried the direct link, the DOI link, Unpaywall and a Playwright browser download, so each
  failing paper costs roughly 30 to 60 seconds of one of the three parse slots. In run 6, five failing papers were a large part of a 4m 28s parsing phase.
- **Most of these papers are free to read.** By OpenAlex / Unpaywall: 7 open access with a PDF link, 11 open access with a landing page only,
  **only 5 closed access**, 1 unknown. The pipeline still fails on them because of how it asks, not because they are paywalled.
- Why they fail: 24 papers by the error of the last attempt: HTTP 403 for 10 (publisher bot protection) and an HTML landing page instead of a PDF for 14.

## 2. What the test of three cheap fixes showed (24 papers, from the laptop)

The three changes: (a) decide by the first bytes (`%PDF-`) instead of the content-type, (b) when the answer is an HTML page, read the PDF address from its
`citation_pdf_url` meta tag (a standard tag most publishers and repositories include), (c) also try the other open-access copies listed by OpenAlex and Unpaywall.

| Result | Papers |
|---|---|
| Now fetched as a real PDF | **5** (1 by the first-bytes check, 4 by `citation_pdf_url`: EWA Publishing, Zenodo, osti.gov, a TU Wien repository record) |
| Still failing | 19 |

Of the 19 that still fail:

| Group | Papers | Why | What could work |
|---|---|---|---|
| **HTTP 403 on an open-access PDF** | MDPI (2), ACM OA article, MIT Press / Computational Linguistics, Preprints.org, TechRxiv, plus the 403 on the Towards Optimal ACM survey (7 to 8 in total) | the publisher blocks non-browser clients (bot protection); other OA copies are blocked too | a real browser session (the Playwright fallback exists but failed), or fetching from another machine; unproven |
| **JavaScript landing pages** | IEEE Xplore (2, gold OA), OSF preprints (2), Zenodo (1), jaicc, an Arabic-finance paper (about 7) | the HTML has no PDF link; the PDF address needs site logic | site rules: IEEE `stampPDF/getPDF.jsp?arnumber=`, OSF API `api.osf.io/v2/preprints/<id>/` -> file link, Zenodo `api/records/<id>`; each helps a handful of papers |
| **Closed access** | ACM (2), SAGE, two small journals (about 5) | needs a subscription | the campus host may be entitled (the same way it is for Scopus); not tested |

## 3. The list (24 papers)

Columns: `failed` = number of runs the paper failed in; `cause` = group above; `fix now` = the cheap fix that fetched it in the test.

| # | Paper | Publisher | Access | Last error | failed | cause | fix now |
|---|---|---|---|---|---|---|---|
| 1 | Towards Optimal Speculative Decoding: A Comprehensive Survey on Optimi | ACM | open access, landing page | HTTP 403 | 4 | 403 bot block | - |
| 2 | Hallucination Mitigation for Retrieval-Augmented Large Language Models | MDPI | open access, landing page | HTTP 403 | 4 | 403 bot block | - |
| 3 | Optimizing LLM Inference: Metrics that Matter for Real Time Applicatio | SRC / jaicc | open access, PDF link | HTML landing page instead of a PDF | 4 | JS landing page (no PDF link in HTML) | - |
| 4 | CRUD-RAG: A Comprehensive Chinese Benchmark for Retrieval-Augmented Ge | ACM | CLOSED ACCESS | HTTP 403 | 2 | closed + 403 | - |
| 5 | A Survey of Hallucination Problems Based on Large Language Models | EWA Publishing | open access, landing page | HTML landing page instead of a PDF | 2 | fixable now | landing-page citation_pdf_url |
| 6 | Enhancing the Precision and Interpretability of Retrieval-Augmented Ge | IEEE | open access, landing page | HTML landing page instead of a PDF | 2 | JS landing page (no PDF link in HTML) | - |
| 7 | Hybrid Speculative Decoding in RAG: When Do the Pros Outweigh the Cons | IEEE | open access, landing page | HTML landing page instead of a PDF | 2 | JS landing page (no PDF link in HTML) | - |
| 8 | Runtime-Controlled Evaluation of Speculative Decoding Methods | MDPI | open access, landing page | HTTP 403 | 2 | 403 bot block | - |
| 9 | EXPLORING HALLUCINATIONS IN LARGE LANGUAGE MODELS (LLMs): A SYSTEMATIC | Zenodo | open access, landing page | HTML landing page instead of a PDF | 2 | fixable now | landing-page citation_pdf_url |
| 10 | Reducing AI RAG Hallucination by Optimizing Routing Techniques | osti.gov | unknown | HTML landing page instead of a PDF | 2 | fixable now | landing-page citation_pdf_url |
| 11 | LARGE LANGUAGE MODELS AS CLINICAL REASONING ASSISTANTS: CAPABILITIES,  | 10.53858 | CLOSED ACCESS | HTML landing page instead of a PDF | 1 | closed access | - |
| 12 | Quantum-Enhanced Retrieval-Augmented Generation for Hallucination Redu | 10.63328 | CLOSED ACCESS | HTML landing page instead of a PDF | 1 | closed access | - |
| 13 | A Substring Extraction-Based RAG Method for Minimising Hallucinations  | ACM | CLOSED ACCESS | HTTP 403 | 1 | closed + 403 | - |
| 14 | LLM Hallucinations in Practical Code Generation: Phenomena, Mechanism, | ACM | open access, PDF link | HTTP 403 | 1 | 403 bot block | - |
| 15 | From Hallucinations to Help: Can Retrieval‑Augmented Generation (RAG)  | OSF Preprints | open access, PDF link | HTML landing page instead of a PDF | 1 | JS landing page (no PDF link in HTML) | - |
| 16 | Hallucination Reduction in Large Language Models with Retrieval-Augmen | OSF Preprints | open access, landing page | HTML landing page instead of a PDF | 1 | JS landing page (no PDF link in HTML) | - |
| 17 | Hallucinations in LLMs: Types, Causes, and Approaches for Enhanced Rel | OSF Preprints | open access, PDF link | HTML landing page instead of a PDF | 1 | fixable now | original URL (magic-byte check) |
| 18 | A Survey on Hallucination in Large Language Models: Definitions, Detec | Preprints.org | open access, PDF link | HTTP 403 | 1 | 403 bot block | - |
| 19 | Reducing hallucination in medical question answering: A comparative st | SAGE | CLOSED ACCESS | HTTP 403 | 1 | closed + 403 | - |
| 20 | Speculative Decoding and Cache Reuse | Zenodo | open access, landing page | HTML landing page instead of a PDF | 1 | JS landing page (no PDF link in HTML) | - |
| 21 | 🧜Siren’s Song in the AI Ocean: A Survey on Hallucination in Large Lang | direct.mit.edu | open access, PDF link | HTTP 403 | 1 | 403 bot block | - |
| 22 | Attention Mapping for Hallucination Reduction in Arabic Financial Usin | doi.org | open access, landing page | HTML landing page instead of a PDF | 1 | JS landing page (no PDF link in HTML) | - |
| 23 | Real-time Prevention of Factual Hallucinations in Retrieval-Augmented  | doi.org | open access, landing page | HTML landing page instead of a PDF | 1 | fixable now | landing-page citation_pdf_url |
| 24 | Retrieval Augmented Generation: A Simplified Approach to Its Operation | techrxiv.org | open access, PDF link | HTTP 403 | 1 | 403 bot block | - |

Counts by cause: {'403 bot block': 7, 'JS landing page (no PDF link in HTML)': 7, 'closed + 403': 3, 'fixable now': 5, 'closed access': 2}.

## 4. What I would do, in order of value

1. **Remember failures (negative cache).** 16 of 40 failure events repeated a known failure, and the same papers (for example "Towards Optimal Speculative Decoding",
   "Hallucination Mitigation for RAG", "Optimizing LLM Inference") fail in every run. Store a failure marker per paper (arXiv id / DOI / title key, with the error and a
   date) and skip the paper for some days, replacing it by the next-ranked paper at once. Saves most of the wasted parse-slot time without touching any download logic.
2. **Decide by the first bytes, and follow `citation_pdf_url`.** Small, safe change in `_download_pdf` that fixed 5 of the 24 in the test (21%) and should generalise to other
   publishers and repositories that serve PDFs with a generic content-type or hide the PDF address in a meta tag.
3. **Try every open-access location** that OpenAlex and Unpaywall list for a DOI (not only the first), after the direct link. Did not rescue any paper on top of (1) and (2) in this
   sample, but costs nothing when it is not needed.
4. **Site rules for IEEE, OSF and Zenodo** (about 5 papers, three small pieces of code).
5. **Test the campus host as the downloader.** Let Docling fetch the URL itself from the host (`sources: [{"kind": "http", ...}]`) or add a small download endpoint to the wrapper.
   It would remove the upload of every PDF over Tailscale and might get the closed-access papers (ACM, SAGE). It will not fix the bot-blocked open-access ones. Unproven; needs a test.

## 5. Caveats

- The log covers 11 start-ups, some of them aborted; failures are counted per "All PDF URLs failed" line, each from one paper in one run.
- Open-access status is what OpenAlex and Unpaywall report today; "open access, landing page only" can still sit behind a click-through or a login.
- The feasibility test ran from a home network without a browser; a failing result there does not prove the paper is unreachable from the host.

## 6. Implemented (2026-10-12)

Items 1 and 2 of section 4 are built:
- **Download fix**: first-bytes `%PDF-` check and `citation_pdf_url` / `<link type="application/pdf">` following in `_download_pdf`. The real agent code now downloads
  **5 of the 24** papers that failed (EWA Publishing, Zenodo, osti.gov, TU Wien repository, one OSF preprint); the same 5 as in the test.
- **Failure memory**: `pdf_failures` table (migration 011), `PDF_FAILURE_TTL_DAYS` (7), `DOWNLOADER_VERSION` (2). Lasting failures (HTTP 403 / 404 / 410 / 451, HTML landing page,
  over-size file) are recorded and skipped for 7 days; transient errors are not. Papers with a recorded failure are tried last when the top papers are chosen.
- Tested offline with a fake web server (octet-stream PDF, landing page with and without a PDF link, `<link>` tag, JSON, 403, 404, size cap) and with the failure memory
  (record, skip, transient not recorded, TTL expiry, older downloader version ignored, clear on success, switch-off, selection order). Not yet seen in a full pipeline run;
  migration 011 must be applied for the memory to persist between runs.
- Still open: the 19 papers above (bot-blocked open access, JavaScript landing pages, closed access) and the host-as-downloader test (item 5).

## 7. Can Docling fetch the PDFs itself, and does the campus network help? (2026-10-12)

Tests run from the dev laptop while it was connected to the campus network (public IP 103.55.110.x, the same range as the host and the friend's machine);
`docling_url_fetch_test.json` has the per-paper result.

**Campus network from the laptop.** Scopus COMPLETE view works from the laptop (abstracts, full authors): the entitlement follows the campus IP range. The same
download test as in section 6 gave exactly the same **5 of 24**: the HTTP 403 papers (ACM, MDPI, MIT Press, Preprints.org, TechRxiv, SAGE) are still refused, so those
403s are bot protection, not a missing subscription. Changing the request headers (browser User-Agent, `Accept: application/pdf`, no User-Agent, python-requests style)
changed nothing for any of the 24.

**Docling fetching the URL itself** (`sources: [{"kind": "http", "url": ...}]` on the host's Docling, OCR off):
- It works: the arXiv control came back as 50,465 characters in 6 s.
- On the 24 formerly failing papers it produced a full-length document (15,000+ characters) for **2**: one OSF preprint (our downloader gets that one now too) and one
  paper that **our downloader cannot get: "Large Language Models as Clinical Reasoning Assistants" (65,335 characters)**. That one is not a PDF: the DOI link leads to
  a journal page whose HTML contains the full article with references (264 KB of HTML; our client receives the same page and rejects it because it is not a PDF).
  Docling converts HTML as well as PDF.
- It does not get past the bot protection: every HTTP 403 paper (ACM, MDPI, Preprints.org, SAGE, MIT Press, TechRxiv) failed there too, from the campus host.
- It reports `success` for landing pages and converts them as documents: 5 papers came back with only 267 to 7,777 characters (an abstract page). So a length check is
  needed (full-text documents here were 30,000 to 65,000 characters, abstract pages 5,000 to 8,000).
- Docling's fetch does not reproduce our citation_pdf_url fix (it converted the EWA, osti.gov and TU Wien landing pages as short HTML pages).

**What fetching on the host saves.** The same PDFs through the two routes (laptop downloads from arXiv and uploads the file to the host, against the host fetching the URL):

| PDF | laptop download + upload and convert | host fetches by URL |
|---|---|---|
| 0.5 MB | 10.4 s | 6.6 s |
| 2.0 MB | 28.3 s | 16.6 s |
| 1.7 MB | 10.5 s | 6.5 s |
| average | 16.4 s | 9.9 s |

About 6.5 s per paper (about 40%), more for large files. This supports the earlier suspicion (report 3, section 10) that sending each PDF from the laptop over Tailscale is a
large part of the pipeline's per-paper time.

**Conclusions.** (1) Docling-by-URL does not solve the 403s and does not make the campus IP useful for downloads. (2) It does save about 6.5 s per paper for publicly
fetchable PDFs, and (3) it can read full-text HTML articles, which recovers one more paper in 24. (4) The pipeline also sends the PDF to PDFFigures, which takes only an
uploaded file; with host-side fetching the figures would be skipped (Stage 3 does not use them).
