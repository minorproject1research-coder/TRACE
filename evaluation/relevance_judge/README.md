# Relevance Judge Benchmark

Everything about how TRACE's **abstract relevance judge** (Stage 2 of the Abstract Relevance Filter) is evaluated:
the dataset, how it was built, how it was labeled, what we learned along the way, and how to run the benchmark.

**Dataset on Hugging Face:** https://huggingface.co/datasets/minorproject-research/trace-relevance-judge (public, MIT-licensed annotations, 360 labeled rows)

```python
from datasets import load_dataset
ds = load_dataset("minorproject-research/trace-relevance-judge", split="test")
```

> **Status (2026-10-10):** the dataset (360 labeled rows) is finished and published, and **12 candidate models have been benchmarked**
> (10 completely, 2 partially). Best overall: GLM-5.3 / GLM-5.3-flash (95.3% accuracy, online); best local: Qwen3.5-9B (90.8%).
> Three results are limited by the test setup rather than by the models. See [Benchmark results](#10-benchmark-results) and [Next steps](#13-next-steps).
>
> **Decision (2026-10-10): the production relevance judge will be Qwen3.5-9B (Q8_0, served locally through Ollama), chosen for its latency** (see [10.4](#104-recommendations)).

---

## 1. Why this exists

TRACE retrieves many candidate papers per sub-question and must not spend the expensive PDF download + Docling + PDFFigures
step on irrelevant ones. `apps/api/agents/stage2_retrieval/relevance_filter.py` therefore filters papers by their abstract in two stages:

| Stage | What it does | Cost |
|---|---|---|
| 1. Embedding pre-filter | `BAAI/bge-base-en-v1.5` cosine similarity between the sub-question and each abstract; keep `>= min_similarity` (0.56 in `filter_relevant`), top 20 | very cheap, runs on every candidate |
| 2. LLM judge (optional, `USE_LLM_JUDGMENT`) | Prompt with sub-question + title + abstract, get `{"relevant": bool, "confidence": 0-1, "reason": "one line"}`; pass if `relevant and confidence >= 0.6` | one small-model call per shortlisted paper |

The judge was originally planned to be the fine-tuned Squeezer (Qwen3.5-3B), with a small Groq model (`llama-3.1-8b-instant`) as a placeholder. This benchmark exists to
**choose the judge model empirically** instead of guessing: every candidate model gets the same prompt on the same labeled papers and is scored against the labels.
**Outcome:** the production judge will be **Qwen3.5-9B**, picked for latency (section 10.4). The code in `relevance_filter.py` still calls the Groq placeholder until it is switched (section 13).

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
| `run_judge_benchmark.py` | Step 3: run candidate models over the dataset and score them (command line) |
| `relevance_judge_benchmark.ipynb` | Same benchmark as a self-contained notebook: loads the dataset from Hugging Face, tests the models one by one, saves each model's results as it goes and skips models already tested (see 9.3b) |
| `models.json` | Model list (Ollama tags / NVIDIA ids / `think` settings) |
| `prelabel.py` | **Alternative, automated** labeling route (strong LLM + `review_queue.csv`). Not used for the final labels |
| `upload_to_huggingface.py` | Publishes the dataset to the Hugging Face Hub (see section 11) |
| `hf_dataset_card.md` | Template of the Hugging Face dataset card; statistics are filled in from the data at upload time |
| `results/` | Per model: `<model>.jsonl` (raw per-row answers), `<model>.summary.json`; plus `summary.csv` / `summary.md` (see section 10) |
| `analyze_results.py` | Reproduces every number in section 10 from `results/` and the dataset (significance tests, confidence, ensembles, cascade, label audit) |

**Not in git:** `dataset.jsonl`, `candidates.jsonl`, `labels/` and `raw/` are listed in `.gitignore`, so they are absent from a fresh clone of the GitHub repo. The
finished dataset is published on Hugging Face at https://huggingface.co/datasets/minorproject-research/trace-relevance-judge (section 11);
`raw/` is only a regenerable API cache.

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

### 9.3b Notebook version

`relevance_judge_benchmark.ipynb` does the same job without needing the local `dataset.jsonl`: it loads
`minorproject-research/trace-relevance-judge` from Hugging Face, then tests each model in `models.json` (or the built-in list) in turn.

- Each answer is appended to `results/<model>.jsonl` the moment it arrives, so a stopped run loses nothing.
- **Re-running skips models that are already fully tested**; an interrupted model resumes with only its missing rows; rows that failed (timeouts, network) are retried.
  To test a model again from scratch, put its name in `FORCE_RERUN`; to test only some models use `RUN_ONLY`; `LIMIT = 30` gives a quick smoke test.
- Models that cannot run (Ollama not reachable, tag not pulled, `TODO` id, no `NVIDIA_API_KEY`) are skipped with the reason.
- It uses the same result format as `run_judge_benchmark.py`, so `results/` can be shared. It also reports the hard-band (similarity 0.6-0.8) accuracy and F1,
  saves `summary.csv` / `summary.md`, draws a chart against the baselines and lists where the best model disagrees with the labels.

Needs `pip install datasets httpx python-dotenv pandas tqdm matplotlib` (the first cell runs it) and a Jupyter kernel (`pip install ipykernel` in the project venv).

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

## 10. Benchmark results

Run on 2026-10-08 and 2026-10-09 with `relevance_judge_benchmark.ipynb`: 12 models, one pass over all 360 rows, the production judge prompt (abstract cut at
2,500 characters), temperature 0.1. Raw answers: `results/<model>.jsonl`; table: `results/summary.md`. Every number below is reproduced by
`python -m evaluation.relevance_judge.analyze_results`.

### 10.1 How the run was done

- Local models through Ollama on a 16 GB GPU (RTX 2000 Ada); online models through the NVIDIA free endpoints with `max_tokens = 1024`.
- An unparseable or empty answer counts as "not relevant", as it would in production.
- 10 models were tested on all 360 rows. `nemotron-3-ultra-550b` has 348 rows (12 missing) and `kimi-k3` only 15, so their numbers are partial.
- One run per model, so run-to-run variation is not measured.

### 10.2 Leaderboard (sorted by F1; positive class = relevant)

| Model | Rows | Valid JSON | Accuracy (95% CI) | Precision | Recall | F1 | Rejects irrelevant | s / paper (median / p95) |
|---|---|---|---|---|---|---|---|---|
| glm-5.3-flash (online) | 360 | 99% | 0.953 (0.93-0.97) | 0.951 | 0.979 | 0.965 | 90% | 57.2 / 129.9 |
| glm-5.3 (online) | 360 | 93% | 0.953 (0.93-0.97) | 0.974 | 0.954 | 0.964 | 95% | 5.6 / 27.6 |
| qwen3.5-9b-q8 | 360 | 100% | 0.908 (0.87-0.93) | 0.889 | 0.983 | 0.934 | 76% | 2.3 / 2.6 |
| nemotron-3-ultra-550b (online, partial: 348 rows) | 348 | 99% | 0.902 (0.87-0.93) | 0.916 | 0.939 | 0.927 | 83% | 10.6 / 40.2 |
| gemma4-e4b-q8 | 360 | 100% | 0.889 (0.85-0.92) | 0.863 | 0.987 | 0.921 | 70% | 14.9 / 19.1 |
| qwen3.5-4b-q8 | 360 | 100% | 0.875 (0.84-0.91) | 0.853 | 0.979 | 0.912 | 67% | 1.4 / 1.6 |
| phi4-14b-q4km | 360 | 100% | 0.853 (0.81-0.89) | 0.822 | 0.992 | 0.899 | 59% | 2.4 / 2.9 |
| gpt-oss-20b | 360 | 100% | 0.864 (0.82-0.90) | 0.905 | 0.886 | 0.896 | 82% | 1.9 / 2.7 |
| qwen3-8b-q8 | 360 | 100% | 0.844 (0.80-0.88) | 0.811 | 0.996 | 0.894 | 55% | 2.1 / 2.5 |
| phi4-mini-q8 | 360 | 100% | 0.800 (0.76-0.84) | 0.770 | 0.992 | 0.867 | 43% | 1.0 / 1.2 |
| nemotron-3.5-lightning-30b (online) | 360 | **61%** | 0.786 (0.74-0.83) | 0.965 | 0.700 | 0.812 | 95% | 23.3 / 54.3 |
| kimi-k3 (online, partial: 15 rows) | 15 | 73% | 0.667 (0.42-0.85) | 0.714 | 0.625 | 0.667 | - | 140.5 / 294.9 |

"Rejects irrelevant" is the share of the 123 irrelevant papers the model says "not relevant" to. Baselines on the same data: always answering "relevant" scores
**65.8%**; the production embedding pre-filter (similarity >= 0.56) scores **71.1%** and lets 103 of the 123 irrelevant papers through (it rejects 16%); the best
single similarity threshold (0.72, chosen on this same data, so optimistic) scores **83.3%**.

### 10.3 What the results show

1. **Tiers, and what is statistically solid.** Top: GLM-5.3 and GLM-5.3-flash (identical, p = 1.0). Then Qwen3.5-9B and Gemma (p = 0.28, not separable). Then Qwen3.5-4B,
   gpt-oss-20b, phi4-14b and Qwen3-8B, which cannot be told apart at this size. Last: phi4-mini (below the 83.3% single-threshold baseline) and nemotron-lightning (see point 3).
   With paired exact McNemar tests, only three differences survive a Holm correction across the 14 comparisons made: Qwen3.5-9B > phi4-mini, Qwen3-8B > phi4-mini and
   gpt-oss-20b > nemotron-lightning (the last because of its invalid replies). GLM > Qwen3.5-9B (p = 0.005 to 0.009) narrowly misses the corrected threshold, and
   Qwen3.5-9B > Qwen3.5-4B or > gpt-oss (p about 0.03) do not survive it, so read those as suggestive.
2. **Local models are lenient: they say "relevant" too readily.** Recall is 98-99.6% for every local model except gpt-oss-20b (0.886), but they reject only 43-76% of the
   irrelevant papers (gpt-oss-20b: 82%; GLM: 90-95%). Their errors are almost all false positives. For a pipeline where a missed paper never reaches parsing this is a
   defensible trade, but it means the judge removes less than the accuracy figure suggests.
3. **Three results are limited by the test setup, not only by the models.**
   - **GLM-5.3:** all 24 invalid answers are *empty* (probably all tokens spent on hidden reasoning within `max_tokens = 1024`); 9 of them were relevant papers. On the 336
     it answered it scores 97.6% accuracy (F1 0.983).
   - **nemotron-lightning:** 139 invalid answers, mostly long reasoning text with no usable JSON or a truncated one. On the 221 it finished it scores 96.8% (F1 0.979). The
     answered subset may be the easier rows, so this is not its true accuracy.
   - **kimi-k3:** the replies are garbled (for example `<|open|>{"=":}`), so the model id or output format is probably wrong; only 15 rows exist.
   - **nemotron-3-ultra:** 12 rows are missing; on the 348 it scores 90.2%, equal to Qwen3.5-9B (p = 1.0) but about 6 times slower.
4. **Most of the gap between models is on the borderline rows.** On the 252 rows whose label confidence is >= 0.9, accuracy is 99.6% (GLM-flash), 98.8% (GLM-5.3),
   98.4% (Gemma), 97.6% (Qwen3.5-9B), 96.4% (Qwen3.5-4B), 96.0% (phi4-14b), 95.2% (gpt-oss), 94.8% (Qwen3-8B), 90.5% (phi4-mini). On the 325 rows with label confidence
   >= 0.7: GLM-flash 98.5%, GLM-5.3 96.6%, Qwen3.5-9B 93.8%, Gemma 93.5%, Qwen3.5-4B and phi4-14b 90.5%, gpt-oss 89.8%, Qwen3-8B 88.6%, phi4-mini 84.0%. Twelve of GLM-flash's 17 errors
   fall inside the 35 low-confidence rows, so it is close to the ceiling this labeling allows.
5. **The confidence field is mostly unusable for the local models.**
   - The production rule `confidence >= 0.6` never changes a decision: F1 with and without it is identical for every model.
   - Qwen3.5-4B answers 0.95 on 321 of 360 rows, so there is nothing to threshold (AUROC 0.847). GLM's confidence is informative (AUROC 0.995 and 0.990), Gemma's 0.951, Qwen3.5-9B's 0.931.
   - Qwen3-8B and phi4-mini state a confidence of 0.3 or lower on **100%** of their "not relevant" answers: they read "confidence" as P(relevant) instead of "how sure I am of my verdict".
     The prompt is ambiguous here; re-reading their numbers that way lifts AUROC from 0.830 to 0.889 and from 0.774 to 0.858. It distorts their Brier scores, not their decisions.
6. **Cheap improvements.**
   - **Cascade with the embedding filter:** reject below similarity 0.6 (32 rows, 2 relevant) and accept at 0.8 or above (74 rows, 72 relevant), and call the LLM only on the other 254 rows:
     this saves **29% of LLM calls** with an accuracy change of -0.3 to +1.4 points. (Thresholds picked on this data.)
   - **Two local models that must agree** (Qwen3.5-9B AND Gemma) reach 92.8% accuracy, F1 0.947, rejecting 84% of irrelevant papers. It beats Gemma alone (p = 0.003) and is borderline against
     Qwen3.5-9B alone (p = 0.065), at double the latency. Majority votes of 3 or 5 local models do not help (89-91%).
   - **A similarity gate on a single model** (threshold chosen by cross-validation) adds only +0.3 to +3.3 points.
7. **Models fail where the topic boundary is a judgment call.** Lowest mean accuracy over the complete models: MoE architectures (0.74), KV-cache/efficient attention (0.77), self-supervised
   ASR (0.78), RAG and hallucination rates (0.78), RL sample efficiency (0.78), dense retrieval (0.81), multi-agent LLMs (0.81), 4-bit PTQ (0.82). These are the topics where the labels apply a strict
   "adjacent method is not relevant" rule (MoE serving systems, Whisper ASR, re-rankers). Sixteen rows are misjudged by at least 7 of 9 judges, and almost all are my low-confidence "not relevant" calls,
   so these are mainly **policy disagreements, not clear mistakes**. The exceptions: `sq29_09` is probably a label error (all 9 models say "not relevant" because the abstract is off-topic and the label
   was given from the title; see 8.1), and `sq15_09` is a genuine model error (diffusion used for spin-glass sampling; 7 of 9 say relevant).
8. **Source matters.** The arXiv rows (92, only 45% relevant) are harder for small models: Qwen3.5-9B 0.891 vs 0.921 on OpenAlex, Qwen3.5-4B 0.826 vs 0.893, phi4-mini 0.717 vs 0.822; GLM-5.3 is steady (0.957 vs 0.946).
9. **Speed.** Local models take 1.0-2.4 s per paper (median) except Gemma, at 14.9 s. Online: GLM-5.3 5.6 s median (p95 27.6, worst 146), GLM-flash 57 s, nemotron-ultra 10.6 s, nemotron-lightning 23.3 s,
   kimi 140 s; these include queueing on free endpoints and are not representative of a paid or local deployment. Gemma's time is tightly clustered (p95 19.1 s) and its replies are normal length, so it is
   probably compute- or memory-bound rather than reasoning; a GPU-memory problem was found on that machine (7.6 GB held by a Hyper-V process), which could have forced CPU offload. This is unconfirmed.

### 10.4 Recommendations

- **Decision: Qwen3.5-9B (Q8_0, Ollama) is the production judge, chosen for latency.** The GLM models are more accurate (95.3% vs 90.8%) but are online free endpoints whose latency is long and uneven (GLM-5.3 median 5.6 s, p95 27.6 s, worst 146 s; GLM-5.3-flash 57 s median), and they send paper text off the machine. Among the models that answer in about 2 s or less, Qwen3.5-9B is the most accurate (0.908 vs 0.875 for Qwen3.5-4B, 0.864 for gpt-oss-20b, 0.853 for phi4-14b) and the only one whose confidence carries some signal (AUROC 0.931). It answers in 2.3 s median (p95 2.6 s) with 100% valid JSON. What is given up: it is lenient (recall 0.983, but it rejects only 76% of irrelevant papers) and about 4.5 points less accurate than GLM; the cascade below recovers part of the cost savings.
- **Deployment (2026-10-10): the judge is served from the model server** (vLLM, FP8 weights, one GPU shared with the planner LoRA) and the pipeline calls `POST /judge`. Run through that endpoint, the 360 benchmark papers score accuracy 0.900 / F1 0.927 as returned and **0.914 / 0.938** once replies are repaired, in line with the Ollama result above (0.908 / 0.934), at 0.47 s per paper with 8 parallel workers. 7.8% of replies (28 of 360) were complete verdicts missing only the final `}`; the client repairs them. The wrapper's own parser should do the same.
- **Local judge alternatives:** Qwen3.5-4B (87.5%, 1.4 s) is the fallback if memory or speed is tight; the Qwen3.5 family beats the older Qwen3-8B by 3 points despite being smaller.
- **Put the cascade in front of it** (reject < 0.6, accept >= 0.8, judge the middle): 29% fewer LLM calls at no real accuracy cost.
- **Use GLM as a teacher, not as the production judge:** it is the most accurate and its confidence is trustworthy, but it is an online free endpoint with long and uneven latency. Have it label extra papers and fine-tune the
  Squeezer on them. Keep the 360 benchmark rows out of that training data.
- **Skip** phi4-mini (below the embedding baseline), phi4-14b (heavier and worse than Qwen3.5-4B) and Qwen3-8B; nemotron-ultra is no better than Qwen3.5-9B and much slower.
- **Strict or lenient is a product decision.** If wasted PDF parsing is the main cost, prefer the stricter gpt-oss-20b or the AND-pair; if losing a relevant paper is worse, prefer the lenient Qwen models.
- **Do not rely on `confidence >= 0.6`** with these models; if confidence is wanted, clarify its meaning in the prompt and re-test.

### 10.5 Caveats

- The labels come from a single LLM annotator (section 8.2), 35 rows are contested, and the results depend somewhat on how strictly "adjacent" topics are judged.
- n = 360: a single accuracy has about +/-5 points of uncertainty, and rows within a sub-question are correlated.
- One run per model at temperature 0.1; settings were not identical across models (`think` flags, `max_tokens = 1024` for the online models).
- The 83.3% embedding baseline and the cascade thresholds were chosen on this same data, so both are slightly optimistic.
- Latencies come from different hardware conditions and free shared endpoints and are only indicative.

### 10.6 Reproducing the analysis

```powershell
venv\Scripts\python.exe -m evaluation.relevance_judge.analyze_results            # every section
venv\Scripts\python.exe -m evaluation.relevance_judge.analyze_results signif     # one section
```

Sections: `verify`, `invalid`, `missing`, `signif`, `conf`, `confsem`, `ensemble`, `cascade`, `breakdown`, `audit`, `answered`, `clear`, `latency`. It reads `results/` and the local
`dataset.jsonl` (or the Hugging Face dataset if the file is absent) and writes nothing.

---

## 11. Reproducing the dataset

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

### Publishing the dataset on Hugging Face

The published dataset: https://huggingface.co/datasets/minorproject-research/trace-relevance-judge

`upload_to_huggingface.py` stages and uploads the dataset (data + a generated dataset card + the sub-question list). It needs a Hugging Face **write**
token in `.env` as `HF_TOKEN` (optionally `HF_DATASET_REPO=<username>/trace-relevance-judge`; `pip install huggingface_hub`). The token in `.env` takes
precedence over any system-level `HF_TOKEN`, and the script refuses to upload to an account the token cannot write to.

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

---

## 12. Changes made outside this folder because of this work

- `apps/api/agents/stage2_retrieval/relevance_filter.py`: added `JUDGE_ABSTRACT_CHAR_LIMIT = 2500` and used it in `llm_judge_relevance`.
- `apps/api/agents/stage2_retrieval/paper_retrieval_agent.py`: Semantic Scholar backoff (env-configurable), OpenAlex search (key pool, rerank + semantic,
  sanitising, filters, timeout), fixed de-duplication/merge, IEEE failure logging without the key.
- `apps/api/agents/stage2_retrieval/key_pool.py`: per-key cooldown length and a non-consuming `next_available_in()`.
- `.env.example` and `.omo/PROJECT_ARCHITECTURE.md`: new variables and documentation.

---

## 13. Next steps

0. **Done (2026-10-10): the pipeline now uses the model server** for the judge (`/judge`) and the planner (`/decompose`). To turn the judge on set `USE_LLM_JUDGMENT=true` in `.env`; a full pipeline run with it has still to be verified.
1. **Fix the test setup and rerun the affected models:** raise `max_tokens` (or switch off thinking) for the online models, then redo `glm-5.3` (24 empty answers), `nemotron-3.5-lightning-30b` (139 invalid),
   `nemotron-3-ultra-550b` (12 missing rows) and verify the `kimi-k3` model id. The notebook currently retries only rows that raised an error, not rows with an invalid answer, so a small option
   to drop invalid rows before a rerun is needed.
2. **Label review:** flip or drop `sq29_09` (all models say "not relevant" and the judge sees the off-topic abstract), spot-check the other contested rows, and re-publish the dataset if labels change
   (re-run `merge_labels.py` and `upload_to_huggingface.py --public`).
3. **Decide strict vs lenient** for the production judge and, if wanted, clarify the meaning of `confidence` in the prompt and re-test the affected models.
4. **Check Gemma's speed** (`ollama ps`, look at the `PROCESSOR` column during a run) and rerun it with the GPU memory free.
5. **Build the cascade** into `relevance_filter.py` (reject < 0.6, accept >= 0.8, LLM in between) and measure the saved calls on real pipeline runs.
6. **Optional, if a smaller or faster judge is wanted later:** create training data with GLM on papers that are not in this benchmark, fine-tune a small Qwen3.5 model, and benchmark it here against Qwen3.5-9B (87.5% for the untuned 4B is the starting point). The Squeezer is no longer the planned judge.
7. If two top candidates end up within about 5 points, label a second batch of the same size.
