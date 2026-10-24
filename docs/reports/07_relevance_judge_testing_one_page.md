# Report 7 - Testing the relevance-judge model (one page)

**Question.** Stage 2 keeps a paper only if an LLM judge, shown a sub-question plus a paper's title and abstract, says it is relevant. Which model should be the judge?
Full write-up: `evaluation/relevance_judge/README.md` (section 10). Dataset: `minorproject-research/trace-relevance-judge` on Hugging Face (MIT).

**Test set.** 360 rows = 30 technical sub-questions x 12 real papers from the pipeline's own retrieval, sampled across similarity tiers so hard negatives are included. Every title and abstract
was labelled by an LLM annotator against a written rubric (with confidence and reason; 35 contested rows). 237 relevant (66%), 123 not (34%).

**Method.** 12 models, one pass each over all 360 rows with the production prompt (abstract cut at 2,500 characters), temperature 0.1. Local models via Ollama on a 16 GB GPU, online ones via
free NVIDIA endpoints. Metrics: accuracy, precision, recall, F1, share of irrelevant papers rejected, valid-JSON rate, latency, McNemar tests.

| Model | Accuracy | F1 | Rejects irrelevant | Seconds / paper |
|---|---|---|---|---|
| GLM-5.3 / GLM-5.3-flash (online) | 0.953 | 0.964 / 0.965 | 95% / 90% | 5.6 / 57 (uneven) |
| **Qwen3.5-9B (local)** | **0.908** | **0.934** | 76% | **2.3** |
| Nemotron-3-ultra (online, 348 rows) | 0.902 | 0.927 | 83% | 10.6 |
| Gemma 4 E4B | 0.889 | 0.921 | 70% | 14.9 |
| Qwen3.5-4B | 0.875 | 0.912 | 67% | 1.4 |
| gpt-oss-20b | 0.864 | 0.896 | 82% | 1.9 |
| Phi-4 14B / Qwen3-8B | 0.853 / 0.844 | 0.899 / 0.894 | 59% / 55% | 2.4 / 2.1 |
| Phi-4-mini | 0.800 | 0.867 | 43% | 1.0 |
| Nemotron-lightning (61% valid JSON), Kimi-K3 (15 rows) | limited by the test setup | | | |

Baselines on the same rows: always "relevant" 65.8%; the pipeline's embedding pre-filter alone (similarity >= 0.56) 71.1%, letting 103 of the 123 irrelevant papers through; the best single
similarity threshold (0.72, chosen on this data) 83.3%.

**What it showed.**
- The LLM judge adds a lot: the best local model beats the embedding filter by about 20 points.
- Local models are **lenient**: recall 98 to 99.6%, but they reject only 43 to 76% of irrelevant papers; their errors are almost all false positives.
- Errors sit on borderline rows: Qwen3.5-9B is 97.6% accurate on the 252 rows with confident labels. Qwen3.5-9B, Gemma and Qwen3.5-4B cannot be separated statistically at n = 360.
- The model's own `confidence` is mostly unusable for local models (a `>= 0.6` rule never changed a decision).
- Cheap improvement: reject below similarity 0.6, accept at 0.8 or above and judge only the middle: 29% fewer LLM calls, no real accuracy cost.

**Decision.** **Qwen3.5-9B is the production judge, chosen for latency**: the most accurate model that answers in about 2 s and always returns valid JSON. GLM is 4.5 points more accurate, but it is
an online free endpoint with slow, uneven latency (median 5.6 s, worst 146 s) and it sends paper text off the machine; it is better used as a teacher for labelling.

**Deployment check (2026-10-10).** Served by the model server (vLLM, FP8 weights) at `POST /judge`: the same 360 papers score accuracy 0.900 / F1 0.927 as returned and 0.914 / 0.938 after repairing
replies (28 of 360 were complete verdicts missing the final `}`), at 0.47 s per paper with 8 parallel workers. In pipeline runs it rejects 6 to 18 of 60 shortlisted papers, mostly clearly off-topic
ones, and a judge failure keeps the paper instead of dropping it.

**Caveats.** One LLM annotator; n = 360 gives about +/-5 points; one run per model; online models were limited by `max_tokens = 1024` and free-endpoint queueing; the 83.3% baseline and the
cascade thresholds were tuned on the same data.
