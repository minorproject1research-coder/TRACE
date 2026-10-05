# Relevance Judge Benchmark

Everything about how TRACE's **abstract relevance judge** (Stage 2 of the Abstract Relevance Filter) is evaluated:
the dataset, how it was built, how it was labeled, what we learned along the way, and how to run the benchmark.

> **Status (2026-10-05):** the dataset (`dataset.jsonl`, 360 labeled rows) is finished. The benchmark runner is written and
> smoke-tested on mocks, but **no candidate model has been run on the dataset yet** (see [Next steps](#12-next-steps)).

---

## 1. Why this exists

TRACE retrieves many candidate papers per sub-question and must not spend the expensive PDF download + Docling + PDFFigures
step on irrelevant ones. `apps/api/agents/stage2_retrieval/relevance_filter.py` therefore filters papers by their abstract in two stages:

| Stage | What it does | Cost |
|---|---|---|
| 1. Embedding pre-filter | `BAAI/bge-base-en-v1.5` cosine similarity between the sub-question and each abstract; keep `>= min_similarity` (0.56 in `filter_relevant`), top 20 | very cheap, runs on every candidate |
| 2. LLM judge (optional, `USE_LLM_JUDGMENT`) | Prompt with sub-question + title + abstract, get `{"relevant": bool, "confidence": 0-1, "reason": "one line"}`; pass if `relevant and confidence >= 0.6` | one small-model call per shortlisted paper |

The final judge model is meant to be the fine-tuned Squeezer (Qwen3.5-3B); until it exists a small Groq model
(`llama-3.1-8b-instant`) is a placeholder. This benchmark exists to **choose the judge model empirically** instead of guessing:
every candidate model gets the same prompt on the same labeled papers and is scored against the labels.

Candidates (see `models.json`; tags/ids there are **placeholders to verify**):

- **Local via Ollama:** Qwen3.5-4B (Q8_0), Qwen3.5-9B (Q8_0), Qwen3-8B (Q8_0), Phi-4 14B (Q4_K_M), Phi-4-mini 3.8B (Q8_0), Gemma 4 E4B (Q8_0), gpt-oss-20b (MXFP4)
- **Online via NVIDIA endpoints:** GLM-5.3, GLM-5.3 Flash, Kimi K3, nemotron-3.5-lightning-30b-a3b, nemotron-3-ultra-550b-a55b

---

## 2. Files

| File | Purpose |
|---|---|
| `sub_questions.json` | The 30 technical sub-questions (id, main topic, detail questions) |
| `collect_candidates.py` | Step 1: retrieve papers per sub-question, sample a spread of similarity levels -> `candidates.jsonl` |
| `raw/<sqid>.json` | Cached raw retrieval results per sub-question (makes step 1 resumable) |
| `candidates.jsonl` | 360 unlabeled rows (30 sub-questions x 12 papers) |
| `read_batch.py` | Prints candidate rows for hand-labeling (`python -m evaluation.relevance_judge.read_batch sq01 sq02 ...`) |
| `labels/batch01..10.jsonl` | The hand-written labels (`id`, `relevant`, `confidence`, `reason`), 3 sub-questions per batch |
| `merge_labels.py` | Step 2: validates + merges the label batches into `dataset.jsonl`, prints class balance |
| **`dataset.jsonl`** | **The finished benchmark**: candidates + `label` + `label_source: claude-manual` |
| `common.py` | Shared helpers: judge prompt (imported from production), tolerant verdict parser, jsonl IO |
| `run_judge_benchmark.py` | Step 3: run candidate models over the dataset and score them |
| `models.json` | Model list (Ollama tags / NVIDIA ids / `think` settings) |
| `prelabel.py` | **Alternative, automated** labeling route (strong LLM + `review_queue.csv`). Not used for the final labels |
| `upload_to_huggingface.py` | Publishes the dataset to the Hugging Face Hub (see section 10) |
| `hf_dataset_card.md` | Template of the Hugging Face dataset card; statistics are filled in from the data at upload time |
| `results/` | Created by the runner: `<model>.jsonl` raw outputs and `summary.md` |

**Not in git:** `dataset.jsonl`, `candidates.jsonl`, `labels/` and `raw/` are listed in `.gitignore`, so they are absent from a fresh clone of the GitHub repo. The
finished dataset is published on Hugging Face (section 10); `raw/` is only a regenerable API cache.

All commands run from the **repo root** with the project venv (`venv\Scripts\python.exe -m evaluation.relevance_judge.<module>`).

---

## 3. Pipeline at a glance

```
sub_questions.json
      │  collect_candidates.py   (expand queries -> retrieve -> embed -> tiered sample)
      ▼
candidates.jsonl  (360 rows, unlabeled)
      │  read_batch.py  ->  hand labeling  ->  labels/batchNN.jsonl
      │  merge_labels.py
      ▼
dataset.jsonl     (360 rows, labeled)           <-- the benchmark
      │  run_judge_benchmark.py --models ...
      ▼
results/<model>.jsonl  +  results/summary.md
```

---

## 4. How the dataset was built

### 4.1 Sub-questions

30 technical sub-questions written by hand across ML/NLP, systems, vision, privacy/security, RL and speech (RAG hallucination, LoRA/QLoRA,
4-bit quantization, long-context/RoPE, mixture-of-experts, KV-cache, speculative decoding, RLHF/DPO, LLM-as-a-judge, dense retrieval,
distillation, tool use, chain-of-thought, ViT vs CNN, diffusion sampling, CLIP, GNN over-smoothing, federated learning non-IID,
differential privacy/MIA, adversarial robustness, jailbreaks, code-generation benchmarks, synthetic data, multi-agent LLMs, time-series
transformers, RL sample efficiency, self-supervised ASR, hallucination detection, scaling laws, distributed training).
They are "technical questions only", as requested. Each has 2 detail questions, used only to generate search queries.

### 4.2 Retrieval (no PDF parsing)

For each sub-question `collect_candidates.py`:

1. Expands the topic + detail questions into search query variants with the production `query_expansion.expand` (Groq).
2. Retrieves with the real `PaperRetrievalAgent.retrieve` (arXiv, Semantic Scholar, IEEE Xplore, OpenAlex, merged and de-duplicated).
   Raw results are cached in `raw/<sqid>.json`.
3. Keeps papers with an abstract longer than 200 characters.
4. Embeds sub-question and abstracts with `bge-base-en-v1.5` and records `embedding_similarity`.
5. Samples **12** papers per sub-question from similarity tiers (top/mid/low third of the ranked pool, 42% / 33% / 25%, seed 42) so that
   borderline cases and hard negatives are included, not just the obvious positives.

### 4.3 Why 360 rows

30 x 12 = 360 gives roughly a +/-5 point 95% margin on a single accuracy number: enough to separate a 3B model from a 14B one, not to separate two
models 2 points apart. If two top models end up that close, add a second batch of the same size. The target was >= 100 relevant and >= 100
irrelevant rows; the final split is 237 / 123.

### 4.4 Composition of the final dataset

| Source | Rows | Relevant | Relevant rate |
|---|---|---|---|
| OpenAlex | 242 | 176 | 73% |
| arXiv | 92 | 41 | 45% |
| Found by several sources ("both") | 16 | 15 | 94% |
| Semantic Scholar | 10 | 5 | 50% |
| IEEE Xplore | 0 | - | (key returned HTTP 403 during collection) |

Years: mostly 2023-2026 (about two thirds), with older papers present. Abstracts: median ~1,280 characters, 99.7% fit inside the
2,500-character judge limit (one OpenAlex abstract is 8,969 characters).

---

## 5. How the labels were made

### 5.1 Who and how

The labels were written **by Claude (an LLM) reading every title and abstract by hand** in 10 batches of 3 sub-questions (36 rows each), not by a
scripted model call and not by a human. This was chosen to get the best possible labels instead of a cheap automated pass. An automated route
(`prelabel.py`, Groq `gpt-oss-120b`, with a `review_queue.csv` for human overrides) was started first and **abandoned** after 30 rows; those partial
labels were discarded and are not part of the dataset.

### 5.2 What the labeler saw

Exactly what the judge sees: the sub-question's **main topic** (not the detail questions), the paper **title**, and the **abstract** truncated to
`JUDGE_ABSTRACT_CHAR_LIMIT = 2500` characters. Labels therefore mean *"relevance as decidable from what the judge is given"*.

### 5.3 The rubric

**Relevant = true** if the paper would be cited as direct evidence or a core reference for the sub-question: it studies, proposes, evaluates or
surveys the specific problem, method or phenomenon the topic names.

**Relevant = false** if it only shares keywords or the broad field, is off-domain, applies the topic as a minor ingredient to a different
problem, or is an adjacent method rather than the topic itself.

### 5.4 Confidence scale

`confidence` is certainty in the label (not probability of relevance):

| Value | Meaning |
|---|---|
| 0.95-0.99 | Unambiguous (core paper, or clearly unrelated) |
| 0.8-0.9 | Clear but with a small caveat |
| 0.6-0.75 | Borderline, a reasonable reviewer might disagree |
| 0.55-0.6 | Genuine coin-flips, flagged deliberately rather than hidden |

35 of 360 rows are below 0.7; 4 are below 0.6.

### 5.5 Consistency rules used for recurring borderline situations

These were applied the same way everywhere so borderline calls are not random:

- **Method matches but models are small/older** (e.g. LoRA or distillation on BERT-scale models): relevant, lower confidence (0.6-0.75).
- **Papers that adapt/analyze/evaluate a named system** (e.g. methods built on CLIP, or evaluating wav2vec): relevant. **Pure application that uses it as-is** with no new insight: not relevant, low confidence.
- **Mixture-of-experts:** papers about the MoE model itself (routing, training, expert structure, pruning, surveys) are relevant; pure serving/scheduling systems and tasks that only use MoE as a target (unlearning, speculative decoding) are not.
- **Detection vs mitigation** (hallucination): mitigation-only surveys/methods are not relevant to a *detection* topic; uncertainty/consistency signals used for detection are relevant at low confidence.
- **Inference vs training:** tensor-parallel work for *inference* is not relevant to *distributed training* (low confidence, since tensor parallelism is in the topic).
- **Weakly vs self-supervised:** Whisper-based ASR papers are not relevant to "ASR with self-supervised representations"; only the wav2vec family is.
- **Models/papers from a different modality or setting** (CNN-only vs ViT, non-LLM multi-agent RL, human judges vs LLM judges, reward-model length bias vs LLM-as-a-judge): not relevant.
- **Title vs abstract mismatches:** label the paper the title names when it is a core reference, with reduced confidence (see 8.1).

Every row carries a one-line `reason`, so any individual call can be audited.

### 5.6 Validation

`merge_labels.py` refuses to write `dataset.jsonl` unless every candidate id is labeled exactly once, `relevant` is a boolean, `confidence` is in
[0, 1] and `reason` is non-empty.

---

## 6. Dataset statistics

- **360 rows**, 30 sub-questions x 12. **237 relevant (66%) / 123 not relevant (34%).**
- Relevant papers per sub-question range from 2 (`sq25`, time-series transformers) to 12 (`sq13`, chain-of-thought); typically 8-10.
- Label confidence: median 0.95; 35 rows < 0.7 (14 relevant, 21 not relevant); 4 rows < 0.6.
- **Majority-class baseline accuracy: 66%.** A judge that always answers "relevant" scores that, so it is the floor to beat.

---

## 7. Insights

### 7.1 The embedding filter alone is already strong; the LLM judge must beat ~83%

Relevance rate by `bge-base` similarity (from the labels):

| Similarity | Rows | Relevant | Rate |
|---|---|---|---|
| < 0.5 | 6 | 0 | 0% |
| 0.5 - 0.6 | 26 | 2 | 8% |
| 0.6 - 0.7 | 59 | 13 | 22% |
| 0.7 - 0.8 | 195 | 150 | 77% |
| >= 0.8 | 74 | 72 | 97% |

A single similarity threshold scores **83.3% accuracy at 0.72** (82.8% at 0.70). The production threshold `min_similarity = 0.56` scores only
**71.1% accuracy**: it keeps every relevant paper (recall 1.00) but lets through **103 of the 123 irrelevant ones (84%)**. So there is a clear job
for an LLM judge, but it only adds value if it clearly beats ~83% and does so on the hard middle band (similarity 0.6-0.8). Judge the models on
that band as well as overall.

### 7.2 Retrieval quality depends heavily on the search provider

OpenAlex papers are relevant 73% of the time, arXiv papers 45%, and papers found by several sources 94%. arXiv's keyword search returns many
off-topic papers for natural-language queries. Agreement across sources is a strong relevance signal worth considering in the pipeline.

### 7.3 Many "irrelevant" rows are hard negatives, which is what makes the benchmark useful

Most irrelevant rows are not random: they are adjacent-topic papers (PTQ for CNNs on a 4-bit-LLM question, reward-model length bias on an
LLM-as-a-judge question, tensor-parallel inference on a distributed-training question). Only a minority are trivial (physics, chemistry).

### 7.4 Production findings discovered while building this

- **The old 1,000-character abstract cut hurt the judge.** 80% of real abstracts are longer than 1,000 characters (median ~1,280), so the cut dropped
  the methods/results half, where relevance is often decided. It was raised to 2,500 (`JUDGE_ABSTRACT_CHAR_LIMIT` in `relevance_filter.py`, shared by the
  filter, the benchmark and the labeler) so labels and models always see the same text.
- **The retrieval de-duplication was silently broken.** `_merge_and_dedupe` stored papers under raw keys but looked them up under prefixed keys,
  so nothing ever merged, `query_variant_matched` never exceeded 1, and papers with neither an arXiv ID nor a DOI were dropped. Fixed: papers are
  registered under every identifier they have and any match merges (arXiv ID without version, lower-cased DOI, normalized title).
- **OpenAlex was added and tuned** (key pool, Bearer auth, type/language filters, `?`/`*` sanitising because OpenAlex returns HTTP 400 for wildcards,
  OR-joined keyword search + AI rerank, plus semantic search). It measurably improved relevance (mean abstract-to-question similarity 0.73 vs 0.67 for arXiv).
  A strict LLM labeler could not separate the search variants on precision (all 0.93-0.95); they differ in *which* papers they return (semantic search
  overlaps the others by only ~1 in 10), so both are used.
- **Semantic Scholar is rate-limited hard without an API key**; exponential backoff with jitter and a configurable policy was added, but a key is needed
  for real throughput. IEEE returned HTTP 403 (key not yet active) and its failure log used to leak the key in the URL (now logs the status only).

The full description of these retrieval changes is in `.omo/PROJECT_ARCHITECTURE.md` (a local-only document: `.omo/` is git-ignored).

---

## 8. Data-quality issues and limitations

### 8.1 Rows to consider excluding

| Row | Problem |
|---|---|
| `sq22_09` | Title is the Codex paper ("Evaluating Large Language Models Trained on Code") but the abstract is an unrelated LLVM-toolchain project. Labeled relevant, 0.8 |
| `sq29_09` | Title is Kaplan et al. "Scaling Laws for Neural Language Models" but the abstract is about transporting small-scale gains of agentic interventions to frontier scale. Labeled relevant, 0.6 |
| `sq21_03` | Abstract is truncated and contaminated with scraped site text ("Find, read and cite all the research you need..."). Labeled relevant, 0.9 |
| `sq29_11` | Abstract is cut off mid-sentence (252 characters). Irrelevant either way |

These come straight from the upstream metadata (mostly OpenAlex), not from the pipeline.

### 8.2 Known limitations of the labels

- **Single annotator, and it is an LLM.** There is no inter-annotator agreement number and no human verification yet. Labels can be consistently
  biased (for example how strict "adjacent method" is judged). The 35 low-confidence rows are the most contestable; a spot-check of those plus
  ~30 random others is recommended before treating small accuracy differences as real.
- **Relevance is judged against the main topic only**, the same as the judge. Detail questions were ignored, so a paper relevant to a detail question
  but not the main topic is labeled not relevant.
- **Rows within a sub-question are not independent**, so the reported confidence intervals are somewhat optimistic.
- **Source skew:** the pool is mostly OpenAlex + arXiv and recent (2023-2026). IEEE-style journal abstracts are absent, so results may overstate accuracy
  on production input from IEEE/Springer-type sources.
- **Class balance is 66/34**, not the 40/60 originally aimed for, because modern search returns mostly on-topic papers. Look at precision/recall/F1 and
  the hard middle band, not accuracy alone.

### 8.3 Low-confidence rows (< 0.7), the contested ones

```
sq01_03 sq01_04 sq01_08 sq01_09 sq02_05 sq02_10 sq03_03 sq04_05 sq05_02 sq05_03 sq05_04 sq05_07
sq06_00 sq06_01 sq06_11 sq07_06 sq10_11 sq11_06 sq11_09 sq14_00 sq14_05 sq16_11 sq24_01 sq24_02
sq25_00 sq25_04 sq26_01 sq26_02 sq28_01 sq28_07 sq28_10 sq29_09 sq30_00 sq30_04 sq30_08
```

---

## 9. Running the benchmark

### 9.1 Judge prompt (identical to production)

`common.build_judge_prompt` formats `RELEVANCE_JUDGE_PROMPT` imported from `relevance_filter.py` with the sub-question, title and abstract truncated to
`JUDGE_ABSTRACT_CHAR_LIMIT`. If the production prompt changes, the benchmark changes with it.

### 9.2 Backends

- **Ollama** (`http://localhost:11434`, override with `OLLAMA_URL`): native `/api/chat`, JSON mode, `temperature 0.1`, `keep_alive 30m`. Models with
  hidden reasoning take a `think` setting in `models.json` (`false` to disable; gpt-oss needs `"low"`). If Ollama rejects `think` for a model, delete the field for it.
- **NVIDIA** (`https://integrate.api.nvidia.com/v1/chat/completions`): needs `NVIDIA_API_KEY` in `.env`; retries on 429/502/503.

Before running, **verify every tag/id in `models.json`** against `ollama list` and build.nvidia.com; all are placeholders and the GLM/Kimi ids are marked `TODO`.

### 9.3 Commands

```powershell
# quick smoke test on the first 20 rows
venv\Scripts\python.exe -m evaluation.relevance_judge.run_judge_benchmark --models qwen3.5-4b-q8 --limit 20

# one or several models on the full set
venv\Scripts\python.exe -m evaluation.relevance_judge.run_judge_benchmark --models qwen3.5-9b-q8 gpt-oss-20b

# everything in models.json
venv\Scripts\python.exe -m evaluation.relevance_judge.run_judge_benchmark --all

# re-score existing results without calling any model
venv\Scripts\python.exe -m evaluation.relevance_judge.run_judge_benchmark --report
```

Raw outputs go to `results/<model>.jsonl` (resumable: finished ids are skipped); the comparison table is written to `results/summary.md`.

### 9.4 Metrics reported (positive class = relevant)

| Metric | Meaning |
|---|---|
| acc (95% CI) | Accuracy with a Wilson interval; compare against the 66% majority baseline and the ~83% embedding-threshold baseline |
| prec / rec / F1 | On the `relevant` class |
| prod F1 @0.6 | Same, but using the production rule `relevant and confidence >= 0.6` |
| valid JSON | Share of replies that parse into a verdict. Unparseable replies count as "not relevant", as in production |
| Brier | Calibration of confidence-as-probability (lower is better) |
| conf right / wrong | Mean stated confidence when correct vs wrong; a large gap means usable confidence |
| lat mean / p95 | Seconds per paper |

### 9.5 Reading the results

1. A model must beat **66%** (always "relevant") and, to be worth the cost, the **~83%** one-threshold embedding baseline.
2. Prefer high **recall** if the judge is only a second stage: a missed relevant paper never reaches parsing.
3. Check the hard middle band (embedding similarity 0.6-0.8) separately; that is where an LLM can add value.
4. Treat differences smaller than ~5 points as noise at n = 360; if the top two models are that close, add a second labeled batch.
5. Look at **valid JSON** rate and latency: a slightly less accurate model that always returns valid JSON quickly may be the better judge.

---

## 10. Reproducing the dataset

```powershell
# 1. retrieval + sampling (slow: arXiv / Semantic Scholar rate limits; about 3 minutes per sub-question)
venv\Scripts\python.exe -m evaluation.relevance_judge.collect_candidates            # all 30
venv\Scripts\python.exe -m evaluation.relevance_judge.collect_candidates --only sq01 sq02

# 2. labeling
venv\Scripts\python.exe -m evaluation.relevance_judge.read_batch sq01 sq02 sq03     # read, then write labels/batchNN.jsonl
venv\Scripts\python.exe -m evaluation.relevance_judge.merge_labels
```

Retrieval is not bit-for-bit reproducible (search APIs change over time), which is why `raw/` and `candidates.jsonl` are kept: they freeze the exact
papers that were labeled. Do not regenerate `candidates.jsonl` without also redoing the labels.

Environment variables used: `HF_TOKEN` (upload only), `GROQ_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY`, `IEEE_API_KEY`, `OPENALEX_API_KEYS` (or `OPENALEX_API_KEY`),
`NVIDIA_API_KEY`, `OLLAMA_URL`, plus the optional retry settings (`S2_*`, `OPENALEX_*`) documented in `.env.example`.

---

### Publishing the dataset on Hugging Face

`upload_to_huggingface.py` stages and uploads the dataset (data + a generated dataset card + the sub-question list). It needs a Hugging Face **write**
token in `.env` as `HF_TOKEN` (optionally `HF_DATASET_REPO=<username>/trace-relevance-judge`; `pip install huggingface_hub`).

```powershell
# build + validate the upload folder locally, contact nothing
venv\Scripts\python.exe -m evaluation.relevance_judge.upload_to_huggingface --dry-run

# upload as a PRIVATE dataset (asks for confirmation); add --public to publish
venv\Scripts\python.exe -m evaluation.relevance_judge.upload_to_huggingface
```

The data is flattened to plain columns (`relevant`, `label_confidence`, `label_reason`, `quality_flag`, ...) in `data/test.jsonl`; the four problem rows from 8.1 get
a `quality_flag` (use `--drop-flagged` to remove them). The card (`hf_dataset_card.md`) links back to this folder and computes its statistics from the data.
Useful flags: `--exclude-sources semantic_scholar` (if you do not want to redistribute Semantic Scholar-sourced abstracts), `--license`, `--repo-id`, `--out`.
Check the licensing section of the card before making the dataset public.

## 11. Changes made outside this folder because of this work

- `apps/api/agents/stage2_retrieval/relevance_filter.py`: added `JUDGE_ABSTRACT_CHAR_LIMIT = 2500` and used it in `llm_judge_relevance`.
- `apps/api/agents/stage2_retrieval/paper_retrieval_agent.py`: Semantic Scholar backoff (env-configurable), OpenAlex search (key pool, rerank + semantic,
  sanitising, filters, timeout), fixed de-duplication/merge, IEEE failure logging without the key.
- `apps/api/agents/stage2_retrieval/key_pool.py`: per-key cooldown length and a non-consuming `next_available_in()`.
- `.env.example` and `.omo/PROJECT_ARCHITECTURE.md`: new variables and documentation.

---

## 12. Next steps

1. **Verify `models.json`** (Ollama tags, NVIDIA ids, `think` settings) and add `NVIDIA_API_KEY` to `.env`.
2. Smoke-test one local and one online model with `--limit 20`, then run all candidates.
3. Spot-check the 35 low-confidence rows (and ~30 random others); if disagreements are frequent, revise the labels and re-run `merge_labels.py`.
4. Decide whether to drop the four problem rows in 8.1 (and then compare on 356 rows).
5. Read `results/summary.md` against the two baselines (66% always-relevant, ~83% embedding threshold), choose the judge model, and set the production
   confidence threshold (the runner already reports the 0.6 rule; try other thresholds on the saved verdicts).
6. If the top models are within ~5 points, label a second batch of the same size.
7. Once the Squeezer is fine-tuned, benchmark it here against the winner before switching the production reference.
