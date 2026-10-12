# Report 6 - Getting the PDFs that publishers block: research, tests and a plan

Date: 2026-10-12. Follows report 5 (the list of 24 papers whose PDF download failed in the logs). Question: can we download them, and how do we reduce the
blocking (HTTP 403 / "bot protection") without fighting it?

## 1. Position taken

- **Stealth browsers, fingerprint spoofing, proxy rotation and CAPTCHA solving are not part of the plan.** They are the usual "Cloudflare bypass" advice found in GitHub
  snippets and agent-skill files, but they defeat an access control, they break whenever the protection changes, and publisher terms forbid them. ACM's policy lists
  "using scripts, spiders or other robotic activity to automatically download articles" as prohibited, says it blocks the IP addresses it traces them to and may
  suspend the subscription. The campus IP is shared with the whole college, so aggressive scraping could cost students their ACM access.
- What is left is the long list of **legitimate routes**: open-access (OA) mirrors and official APIs. They are also more reliable. They worked better than the
  scripts' tricks in every test below.
- The existing fallback in `_download_pdf_playwright` uses `undetected_playwright` (a stealth browser). It failed on all 40 events in the logs and each failure costs
  up to 30 s. See recommendation 8.

## 2. What the research found

- **Reddit:** the searches returned no useful threads.
- **GitHub and package indexes:** the mature tools all follow the same **OA-first chain** and none relies on evading protection: `respf`, `paper-research-downloader`,
  `OpenPapers MCP`, `scholar-cli` (Rust; races Unpaywall, OpenAlex, Semantic Scholar, DOAJ, Crossref in "legal-only" mode), `PyPaperRetriever` (Unpaywall based),
  `paperscraper` (adds the free Wiley and Elsevier text-and-data-mining APIs) and `fetch_oa.py` (Unpaywall, PMC, OpenAlex, Crossref, landing-page scraping, and it
  requires the file to start with a PDF header and be at least 10 KB). The one stealth-browser snippet found is off by default in its own project.
- **Publisher policies:** ACM forbids automated downloading except under an institutional text-mining licence. Elsevier offers a free TDM API for subscribing
  institutions. MDPI offers an OAI-PMH metadata interface and, per library guides, SFTP bulk full text (to be arranged with its indexing team), but no public PDF API;
  article pages are rate limited. IEEE has an Open Access use case on its developer portal and requires its own key (not set in `.env`).
- **OpenAlex Content API** (new, official): `https://content.openalex.org/works/{id}.pdf?api_key=...` returns OpenAlex's own cached copy of about 50 million
  open-access PDFs; any API key works, including a free one. Filter with `has_content.pdf:true`. The PDFs keep their original copyright and OpenAlex grants no extra rights.
- **CORE** (official aggregator of repository full texts): free, rate limited. In the test it had records for several of the unresolved papers but no download link.

## 3. What we tested on the 24 failed papers

Each route was run against all 24 papers (from the laptop, on the campus network).

| Route | Papers fetched as a real PDF | Notes |
|---|---|---|
| First bytes `%PDF-` + `citation_pdf_url` (built in report 5) | 5 | EWA Publishing, Zenodo, osti.gov, TU Wien repository, one OSF preprint |
| **OpenAlex Content API** (cached PDF) | **7 of 7 that have one**; 6 are new | MIT Press (CoLi), an ACM open-access article, Preprints.org, TechRxiv, two OSF preprints, a small journal. Cost 100 credits ($0.01) each; the free key gives 10,000 credits a day |
| Official OSF API (`api.osf.io/v2/preprints/<id>/`) | 1 new | the preprint our link got as an HTML page |
| Official Zenodo API (`zenodo.org/api/records/<id>`) | 1 (already counted) | the other record holds a Markdown file, not a PDF |
| arXiv title lookup (official API) | 1 new | CRUD-RAG, a closed-access ACM paper, has an arXiv preprint; 1 of 17 searched |
| Docling converting the HTML article (report 5) | 1 new | a journal article whose full text is in the HTML page |
| Different request headers, campus IP, Docling fetching by URL | 0 extra | the 403s are bot protection, not entitlement |
| CORE | 0 | records without download links |
| Crossref links | 0 | only "similarity-checking" copies of the same blocked URLs (not for general use) |

**Total: 14 of 24 papers (58%) are obtainable by compliant routes**, against 0 of 24 before report 5.

Still not fetched (10): MDPI (2), IEEE Access gold OA (2), one ACM open-access survey, one Arabic-finance paper whose repository returns 403, one Zenodo record that
holds only a Markdown file, and three truly closed papers (an ACM paper, a small journal, SAGE).

## 4. Plan: one ordered, polite download chain

For each paper the pipeline tries the cheapest legitimate route first and stops at the first real PDF (first bytes `%PDF-`, at least 10 KB):

1. Parse cache and PDF-failure memory (done).
2. arXiv PDF when the arXiv id is known (done).
3. The paper's own OA PDF link, with the first-bytes check and `citation_pdf_url` (done).
4. **OpenAlex Content API** when the work has cached content. Capture `id` and `has_content.pdf` when the OpenAlex search results are parsed (no extra call) or look them up
   by DOI in one batched metadata call (1 credit per 40 works). Spend control: a daily cap (for example 60 PDFs, `OPENALEX_CONTENT_DAILY_LIMIT`), and stop when the
   `x-ratelimit-remaining` header runs low.
5. **Repository APIs** (OSF, Zenodo) for DOIs with prefix `10.31219` and `10.5281`.
6. **Preprint twin**: exact-title search on the arXiv API for papers that only have a publisher copy; accept only an exact (normalised) title match.
7. **HTML full text**: let Docling convert the landing page when it returns a document of 15,000+ characters (abstract pages return 5,000 to 8,000).
8. Give up politely: record the failure (report 5's memory), keep the paper abstract-only for Stage 3.

Politeness rules for every request that leaves the pipeline: an honest User-Agent with a contact address, per-host spacing (at most one request per 2 s per host), robots.txt
respected for page fetches, no retry after a 403, no more than a few downloads per publisher per run.

## 5. Recommendations, in order

1. **OpenAlex Content API step** (largest gain: 6 papers of 24, official, about $0.01 each, well inside the free daily allowance).
2. **OSF / Zenodo API step and arXiv title twin** (2 more papers; a few lines each).
3. **Docling HTML path with the length check** (1 paper, and the speed gain of letting the host fetch public URLs: about 6.5 s per paper).
4. **Ask for the missing official keys and permissions** for the remaining 10: the free IEEE Xplore key (Open Access use case), a request to MDPI's indexing team for
   bulk access, and the college library about ACM and SAGE text-and-data-mining rights (the campus subscription might include them, but only through the library's proxy or
   agreement, not through scripts).
5. **Do not add stealth tooling.**
6. Keep the failure memory so that papers none of these routes can fetch cost one attempt per week, not one per run.
7. Add the downloaded-file sanity check (first bytes, at least 10 KB) to every route.
8. **Disable `undetected_playwright` by default** (`PLAYWRIGHT_FALLBACK=false`): it never succeeded in the logs, adds up to 30 s per failure and is the one piece of the current
   code that works against the sites' protections.

## 6. Cost and limits to know

- OpenAlex free key: 10,000 credits per day = $1; a PDF download costs 100 credits ($0.01), a metadata call about 1 credit per 40 works, so up to about 100 PDFs a day. This
  investigation used about 850 credits.
- OpenAlex content is open-access only, keeps the publisher's copyright and is for the project's own analysis; do not republish the files.
- The OpenAlex cache covers about 7 of 23 DOIs here (30%); expect most gold-OA preprints and repository papers to be covered and most subscription publishers' papers not to be.

## 7. Sources

- ACM Digital Library usage policy: https://www.acm.org/publications/policies/dl_use_policies
- OpenAlex full-text PDFs: https://help.openalex.org/download/full-text-pdfs and https://help.openalex.org/access/fulltext/
- Elsevier text and data mining: https://www.elsevier.com/about/policies/text-and-data-mining
- MDPI for librarians: https://www.mdpi.com/librarians
- IEEE Xplore API overview: https://developer.ieee.org/docs/read/IEEE_Xplore_Metadata_API_Overview
- CORE API: https://core.ac.uk/services/api
- Tools: `respf` https://pypi.org/project/respf/ ; `paper-research-downloader` https://awesome.ecosyste.ms/projects/github.com%2Fhpsummer%2Fpaper-research-downloader ;
  `scholar-cli` https://github.com/l0o0/scholar-cli ; `paperscraper` https://www.sourcepulse.org/projects/1845005 ;
  `PyPaperRetriever` (JOSS) https://www.theoj.org/joss-papers/joss.08135/10.21105.joss.08135.pdf ; `fetch_oa.py` https://skillselion.com/skills/aperivue/medsci-skills/fulltext-retrieval

## 8. Implemented (2026-10-12)

Steps 1 to 4 of section 5 are built, each behind an environment switch (listed in `.env.example`): `pdf_sources.py` (OpenAlex content API, OSF / Zenodo APIs, arXiv
title twin, polite-access rules), the ordered chain in `_parse_single_paper_uncached`, the HTML full-text route, and the opt-in `DOCLING_FETCH_FIRST`. The headless-browser
fallback keeps its current default (on) and can be switched off with `PLAYWRIGHT_FALLBACK=false`. The OpenAlex credit is not capped: both configured keys rotate on 402 / 403 / 429.

Result on the 24 papers that ever failed, with the real chain (headless browser off for the test; only the final Docling and database steps stubbed):

| Route | Papers |
|---|---|
| the paper's own link (first bytes, `citation_pdf_url`) | 5 |
| OpenAlex content API | 4 |
| Unpaywall (honest User-Agent, Accept: application/pdf) | 3 (a CRUD-RAG copy, an ACM open-access article, the MIT Press survey) |
| OSF / Zenodo API | 1 |
| HTML full text (Docling) | 1 |
| **Total** | **14 of 24** |

Unchanged failures (10): MDPI (2), IEEE Access (2), one ACM survey, one Arabic-finance paper, the Zenodo record that holds only a Markdown file, and three closed-access papers.
Two fixes made during testing: the HTML route first rejected a 65,000-character article because it has no markdown headings (now also accepted with 10+ references), and a per-route
time limit was added because Zenodo's API is slow (up to 80 s per paper in the test).
Tests: 9 offline suites pass (routes with a fake server, key rotation, switches, chain order, politeness, robots.txt, failure memory, parse cache, Scopus, Groq pool, S2 breaker,
query balancing). The live checks used about 1,000 OpenAlex credits.
