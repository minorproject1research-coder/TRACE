# Planner determinism and the opt-in plan cache (2026-11-05)

## Question
Runs of the same question started from different sub-questions (run 5 planned "what is X / what is Y / what is Mamba" sub-questions, run 3 planned comparison sub-questions), which made run-to-run comparisons of Stage 2 and Stage 3 meaningless. Can the planner be made reproducible?

## Test
Direct calls to vLLM on the host (`127.0.0.1:8001`, `/v1/completions`), 4 calls per setting, same prompt, after a warm-up call. The prompt had no planner system prompt (a flat-output regime, so the planner's rows below show more divergence than real use).

| Model | Setting | Identical? | First difference |
|---|---|---|---|
| judge (base) | temperature 0 | yes | none |
| judge (base) | temperature 0.8, seed 7 | yes | none |
| judge (base) | temperature 0.8, no seed (control) | no | char 66 |
| planner (LoRA) | temperature 0 | **no** | char 2 |
| planner (LoRA) | temperature 0.8, seed 7 | **no** | char 985 |
| planner (LoRA) | temperature 0.8, no seed (control) | no | char 2 |

Through the real wrapper with the real prompt, three calls at temperature 0 agreed for 611 characters and then diverged.

## Reading
- vLLM honors per-request seeds and is reproducible for the base model on the same server, so the wrapper is not dropping `seed` and batching or the prefix cache is not the cause.
- The LoRA adapter path is the source of the non-determinism (probably the order in which LoRA kernels combine partial sums; not verified).
- A merged-weights planner would avoid the adapter, but the compose file already uses 88% of the GPU, so a second 9B model probably does not fit. Not tried.

## Decision
No seed for the planner. Instead `PLAN_CACHE=true` (default off) stores the parsed plan per question (`.cache/plans`, key = question + `PLAN_CACHE_TAG`) and reuses it. A plan from the Groq fallback is never stored. `scripts/pipeline_run_report.py` shows "Plan source: planner | plan-cache | groq-fallback". Use it for evaluation reruns; leave it off for normal runs.

Files: `apps/api/agents/stage1_planner/plan_cache.py`, `question_generator.generate`, `tests/test_plan_cache.py`.
