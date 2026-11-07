# Report 18: Loop 2, built and tested

Date 2026-11-07. Plan items A2 to A6 of `docs/KNOWN_LIMITS.md`. Code: `apps/api/agents/stage3_summarizer/loop2.py`, wired into `summarizer_node.py`, report fields in `report_service.py`, settings in `.env.example`, tests in `tests/test_loop2.py`, replay tool `scripts/loop2_on_stored.py`. **Off by default (`LOOP2=false`).**

## What it does
After the judge and the coverage check of a sub-question, and before anything is stored, every aspect that is still uncovered is searched again, cheapest source of new evidence first, and the ladder stops for an aspect as soon as it is covered (2 "yes" from 2 sources, the same rule as before):

| Step | Source of new evidence | Cost |
|---|---|---|
| `reselect` | passages of the papers already parsed that the first digest did not read, chosen for the aspect | one digest per paper, no download |
| `pool` | the next-ranked papers of the Stage 2 pool of the sub-question: parse, read the best passages for the aspect | parsing + digests |
| `queries` | new search queries for the aspect (the Loop 2 query step), papers and web pages: retrieve, relevance filter, store, parse, read | retrieval + parsing + digests |

After a step that added sources the sub-question is judged again (the verdict cache makes that cost only the new pairs) and coverage is recomputed. Triage (A1, report 16): an aspect is searched if it has at least 2 yes/partial verdicts or no candidates; aspects with only "no" verdicts are recorded as known gaps without a search. Stop rules (A3): `LOOP2_MAX_ROUNDS` steps per aspect, `LOOP2_MAX_ASPECTS` aspects per sub-question, a time budget (`LOOP2_MAX_SECONDS`), unjudged aspects are never searched, and the ladder stops when every digest of a step failed (Groq limits). What stays uncovered is a **known gap**; the state of every aspect and step is stored in `coverage_results.judge_stats.loop2` (no migration), so the report, the API and the run report read it.

## Tests
- **Unit (offline, 20 tests):** triage, the ladder order and its stop for covered aspects, known gaps, time budget, step settings, dry run, a failing step, tag mapping of the focused digest prompt, the digest-failed stop, a new-vs-empty digest, the report view, the progress event, and the fallback that restores the Stage 3 result when Loop 2 raises. 268 tests pass in all.
- **Bugs found by running it for real** (all fixed, with a regression test where a test could have caught them): a data key called `step` collided with `progress.report`'s own argument and made every Loop 2 call fail (the first full run); the retrieval agent's asyncio locks belong to the first event loop that used them, so every second `asyncio.run` failed (now a new agent per call); the queries step ran the aspects one after the other (468 s for 7 aspects; now side by side); and when all Groq keys were rate limited the ladder kept trying (now it stops).

## Results

### 1. Replay on the stored Stage 3 of Q1 to Q6 (steps `reselect` and `pool`, triage `all`; no database writes)
The stored digests are judged again with the current judge first (a fresh baseline: the judge moves by a pair or two between runs), then Loop 2 runs on them with real Groq digests and the real judge.

| | Aspects | Covered by Loop 2 |
|---|---|---|
| all uncovered aspects | 36 | **14 (39%)**: `reselect` 12, `pool` 2 |
| R1-eligible (>= 2 yes/partial) | 26 | 11 (42%) |
| R1-skipped | 10 | 3 (30%) |
| my labels: answerable / invented or not asked / unsure | 20 / 10 / 6 | 8 (40%) / 2 (20%) / 4 (67%) |

- 7 of the 25 sub-questions went from "not sufficient" to "sufficient" (Q1 two, Q2 two, Q4 two, Q6 one).
- **Precision of what it covered** (I read the covering claims of the 14): 11 are right: by my earlier labels the clearly worded aspects 8 of 8, the off-question ones 2 of 2, the ones I had marked unsure 1 of 4. Overall 79%, below the 80% I wanted. The three wrong ones ("levels of reasoning", "assumptions of the defenses", "how the defenses are compared") are vague aspects where the judge accepted a generic claim next to one good one, which is the weakness of the planner's generic aspects (limits 1.8, 3.12), not of the search.
- Cost: a `reselect` step takes 14 to 70 s per sub-question, `pool` 35 to 106 s.

### 2. Full pipeline with Loop 2 on (Q3, Q2, Q4; `PLAN_CACHE=true`, all three steps, triage `r1`, cap 4 aspects)
| | |
|---|---|
| uncovered aspects after Stage 3 | 22, of which 16 searched (6 skipped by triage or cap) |
| covered by Loop 2 | **8 (50% of the searched)**: `reselect` 2, `pool` 3, `queries` 3 |
| sub-questions that became sufficient | 1 (Q3 "What is quantization ..."); Q2 stayed 3 of 5, Q3 1 of 3, Q4 1 of 4 |
| new sources / new verified findings | `reselect` 33 / 113, `pool` 11 / 43, `queries` 31 / 93 |
| time of Loop 2 | 1342 s in all: `reselect` 122 s, `pool` 107 s, **`queries` 1112 s (83%)**; +5 to +9 minutes per run |
| precision by my reading | 6 of 8 right ("performance" and "compatibility" of Q3 rest on one weak claim each) |

- The `queries` step does what the cheap steps cannot: it covered Q3 "inference speed" (claims such as "up to 2.4x faster") and "robustness", and Q4 "characteristics of a good benchmark", with new on-topic papers ("Which Quantization Should I Use?", "What Makes Quantization for LLMs Hard?", "Benchmark Radar", "Measuring Reasoning Quality in LLMs"). It also costs five times what the two cheap steps cost together, and the queries around Q2's expert-routing aspects found three new papers and three web pages and covered nothing.
- Sufficiency moved little because most sub-questions fail on several aspects, and the planner's invented ones (diversity, security, interoperability) are never searched and keep the sub-question "not sufficient" (B3, limit 1.8).
- The stored report now shows, per sub-question, what Loop 2 searched, which step covered each aspect, and the **known gaps** (`coverage.loop2` in the API; `foundByLoop2Step` on every source it added).

### 3. What I could not finish
- **Q5 and Q6 with Loop 2** are not measured. The Groq keys ran out of quota during the Q4 run (parking times of 285 s, then up to 1500 s per key): the Q4 sub-question 4 loop could not digest anything, the Q5 run lost nearly all of Stage 3 (13 findings, 0 of 4 sub-questions) and I stopped the Q6 run. The Q5 report was deleted as not meaningful; the rows of those runs remain in the database as incomplete runs. They can be run after the quota resets: `PLAN_CACHE=true LOOP2=true python test_pipeline.py "<question>"`.
- **Q1** has no cached plan, so a run would not be comparable to the stored one.
- **A4's blind comparison** (are the new papers better than the old ones?) was not done; only counts, on-topic reading of titles and the precision of the covering claims.
- The frontend does not show Loop 2 yet; the fields and the event are documented in `docs/API_HANDOFF.md`.

## Decisions and settings
- Keep `LOOP2=false` by default: it adds 5 to 9 minutes and roughly 30 to 50 extra Groq digests per run, and Groq quota was the limit that ended this work.
- If it is switched on, `LOOP2_STEPS=reselect,pool` gives 5 of the 8 covered aspects of the full runs (12 of 14 in the replays) at 17% of Loop 2's time; `queries` is the step for aspects the stored papers cannot answer.
- R1 triage stays the default; in these runs every aspect Loop 2 covered was R1-eligible.
