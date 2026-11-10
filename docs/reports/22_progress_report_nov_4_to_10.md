# Report 22: Progress of TRACE, 4 to 10 November 2026

A summary for explaining the work to the supervisor. Every number comes from the run reports in `docs/reports/runs/`, the numbered reports in `docs/reports/` and the git history (`git log --since=2026-11-04`). Where something has only been measured once, it says so.

## 1. What TRACE is, in one paragraph

TRACE is a research assistant. You ask a research question; it splits it into sub-questions (Stage 1), searches papers and the web (Stage 2), reads the sources and writes down findings that each carry a verified quote, then judges whether the evidence answers every part of the question (Stage 3), and finally checks the findings against each other, labelling every claim as supported, partially supported, unverified or contradicted (Stage 4). Stage 5 (the written report) is not built yet. A web app and an API show the run live.

## 2. Where it stood at the start of the period and where it is now

| | 4 November | 10 November |
|---|---|---|
| Stage 1 planner | fine-tuned planner, generic sub-questions | plus a domain anchor and a plan cache, so searches stay in the right field and a repeated question searches the same way |
| Stage 2 retrieval | worked | relevance judge and parallel filtering across sub-questions |
| Stage 3 | summarizer and judge | judge V2, a second search for uncovered aspects (Loop 2), digest and judge caches, sub-questions processed in parallel |
| Stage 4 | separate code, not part of the pipeline | in the pipeline and the API, four labels, caches, runs during Stage 3 |
| Web app and API | none | web app, API, live progress per stage, Loop 2 and fact-check views |
| Tests | | 415 pass |
| Full run on the diffusion vs GAN question | 23m 33s (run 30, 8 November) | 13m 54s (run 32, today), see the caveat in section 6 |

## 3. What was done, by day

**4 to 5 November: making Stage 3 trustworthy.**
- Added the evidence judge V2 and re-judged the stored runs (report 10): V2 covers fewer aspects than V1 (27 of 42 against 31 of 42), because V1 had been judging with a passage taken from the wrong paper. That bug was found and fixed; the numbers got stricter, not better.
- Fixed aspect merging, NUL characters in parsed text and the quote verifier; added the digest cache.
- Added the Stage 1 domain anchor (report 12): without it a question about "transformers" or "state space models" returned electrical transformers and econometrics papers. Added the plan cache so reruns are comparable.

**6 November: web app and API.**
- Built the FastAPI backend (sessions, events, report, papers) and the web frontend; database reads are retried and connection errors answer 503 instead of 404.
- Turned an experimental setting off after it cut digest findings by 65%.

**7 November: Loop 2 and Stage 4 in the pipeline.**
- Loop 2 (reports 14, 18): for an aspect the first pass could not cover, search again, cheapest first: re-read the papers already parsed, then the next papers from the Stage 2 pool, then new queries. Shown in the web app.
- Stage 4 wired into the graph and the API (report 20): claims grouped, quotes checked, opposite claims searched for. The quote-support check now reuses Stage 3's judge where it already said yes: 180 s down to 1.4 s on the first real run. A guard stops the run's Groq calls when the rate limit is hit; contradiction judge hardened; a labelled set of 41 conflict pairs built to measure it.

**8 November: label, parallelism, speed.**
- New Stage 4 label `partially_supported` (a close variant of the claim in another document), a separate document `docs/STAGE4.md`, shown in the web app.
- Judges wait out short Groq limits instead of failing; NLI answers cached on disk; a token meter that records every Groq call by purpose and key.
- Timing study (report 21), then seven parallelism changes, each behind a switch and tested: Stage 4 starts during Stage 3, judge batches run together, sub-questions are judged two at a time, the near-match judge runs beside the conflict check, and the relevance filter runs across sub-questions. Checked with dry runs on stored data: results identical to the old order.
- Found and fixed a real bug: the digest cache was keyed by query id, so a rerun of the same question redid every digest and spent the tokens again.
- Run 31 was stopped when Groq's daily limit was reached (76,617 tokens spent for no result); documented.
- Backend events now carry the sub-question index and real timestamps; the frontend was updated to match.

**10 November: first run with the parallel pipeline.**
- Run 32 (same diffusion vs GAN question): finished cleanly in 13m 54s, no judge errors, no rate-limit breaker, longest Groq pause 37 s. Report and notes in `docs/reports/runs/run_20261110_1308_1e3aa1eb_*.md`.

## 4. Results to quote

- **Time:** 23m 33s (run 30) to 13m 54s (run 32), on the same question.
- **Coverage:** 4 of 4 sub-questions judged sufficient, 121 of 129 findings with a verified quote.
- **Fact check (run 32):** 89 claims: 4 supported, 35 partially supported, 49 unverified, 1 contradicted; 3 disagreements stored, and reading the quotes all 3 are real disagreements between sources. Run 30 had one false conflict in two, so the contradiction judge is not yet reliable: on the 41 labelled pairs it has precision 0.71 and recall 0.56.
- **Groq budget:** 290,782 tokens for the run (7 free keys, daily limit per key). More than half of it is Stage 4.

## 5. Problems found and how they were handled

| Problem | What happened | Status |
|---|---|---|
| Judge looked at the wrong paper's passage | Older coverage numbers were too generous | Fixed, re-measured (report 10) |
| Digest cache keyed by query id | Reruns of a question repeated all digests | Fixed (content-based scope); a rerun is still to be measured |
| Groq daily limit | Run 31 was stopped, tokens wasted | Documented; runs now watched for long rate-limit waits |
| False conflict from the contradiction judge | One of two in run 30 | Prompt hardened, labelled set extended; precision still 0.71 |
| Semantic Scholar rate limit | Search skipped for the run | Designed behaviour, noted in every report |

All open limits are listed in `docs/KNOWN_LIMITS.md`.

## 6. What is not yet proven (say this plainly)

- The 13m 54s is a single run, and part of the saving comes from caches (plan, parsed papers, judge verdicts), not only from the parallel work. The digest cache did not help in this run; a rerun is needed to measure it.
- Stage 4 is now the slowest part: one background worker handled the four sub-questions one after another (about 11 min in total, of which about 6 min after Stage 3 ended). A second worker would save around 3 min; not built.
- Loop 2 on a single aspect took 288 s and decided when Stage 3 ended.
- The pipeline has been run on about seven questions; the conclusions are about those, not about research questions in general.
- The new live view of the parallel events has not yet been checked in a real run through the web app.
- Stage 5, the written report, is not built.

## 7. Next steps

1. Run the question once more through the web app to check the new live view and measure the digest cache.
2. Add a second Stage 4 worker (as a switch) and reduce Stage 4's token use (the same-claim and near-match judges are 41% of the run's tokens).
3. Improve the contradiction judge's precision on real data.
4. Start Stage 5 (the written report), which reads the Stage 4 labels as described in `docs/STAGE4_OUTPUT.md`.

## 8. Two-minute version

"In the last week I turned TRACE from separate stages into one pipeline with a web app. I made Stage 3 stricter and found a bug that had made its coverage too generous. I added a second search for the evidence gaps, and a fact-checking stage that labels every claim and shows a new 'partially supported' label. Then I measured where the time goes and made the stages overlap: the same question went from 23.5 to 14 minutes. The limits: that is one run and partly cached, the contradiction check is only 71% precise, the free Groq quota is tight, and the final written report is the next stage to build."
