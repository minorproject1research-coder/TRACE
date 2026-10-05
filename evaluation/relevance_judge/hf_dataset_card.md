---
license: {{license}}
language:
- en
pretty_name: TRACE Relevance Judge Benchmark
size_categories:
- n<1K
task_categories:
- text-classification
tags:
- relevance-judgment
- abstract-screening
- scientific-literature
- literature-review
- llm-evaluation
- llm-as-a-judge
- information-retrieval
configs:
- config_name: default
  data_files:
  - split: test
    path: data/test.jsonl
---
# TRACE Relevance Judge Benchmark

A small, carefully labeled benchmark for **abstract-level relevance judgment**: given a technical research question and a paper's title and
abstract, decide whether the paper is relevant evidence for that question. It was built to choose the small LLM that acts as the relevance
judge in [TRACE](https://github.com/minorproject1research-coder/TRACE), an automated literature-review assistant, but it is self-contained
and usable to evaluate any model or heuristic on the same task.

- **{{n_rows}} labeled examples** = {{n_questions}} technical sub-questions x 12 papers each
- **{{n_relevant}} relevant ({{pct_relevant}}%) / {{n_not_relevant}} not relevant**, each with a confidence and a one-line justification
- Evaluation only (a single `test` split); not intended for training

**Source code, retrieval pipeline, labeling notes and benchmark runner:**
https://github.com/minorproject1research-coder/TRACE/tree/main/evaluation/relevance_judge

## Task

Binary classification with a calibrated confidence. Input: a research question (the sub-question's main topic), a paper title and an abstract.
Expected output: a verdict `relevant` (true/false), a `confidence` in [0, 1] and a short reason. The reference judge prompt used in TRACE (and in the
benchmark runner) is:

```
You are judging whether a research paper is relevant to a specific research question, based only on its title and abstract.

Research question: {sub_question}

Paper title: {title}
Paper abstract: {abstract}

Judge if this paper is directly relevant and useful as evidence for answering the research question.
Return ONLY a JSON object, nothing else, in this exact format:
{"relevant": true or false, "confidence": a number between 0 and 1, "reason": "one short sentence"}
```

The benchmark runner truncates the abstract to the first **2,500 characters** (covers {{pct_fit}}% of the abstracts here); the labels were written
against exactly that text.

## Dataset structure

Single split `test`, one JSON object per line (`data/test.jsonl`).

| Field                    | Type           | Description                                                                                                                                   |
| ------------------------ | -------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `id`                   | string         | Row id,`<sub_question_id>_<index>` (for example `sq02_02`)                                                                                |
| `sub_question_id`      | string         | `sq01` ... `sq30`                                                                                                                         |
| `sub_question`         | string         | The research question (main topic) the paper is judged against                                                                                |
| `title`                | string         | Paper title                                                                                                                                   |
| `abstract`             | string         | Paper abstract (may be longer than the 2,500-character judge limit; see above)                                                                |
| `year`                 | int            | Publication year                                                                                                                              |
| `source`               | string         | Where the record was retrieved from:`openalex`, `arxiv`, `semantic_scholar`, or `both` (found by several providers)                   |
| `doi`                  | string or null | DOI when known                                                                                                                                |
| `arxiv_id`             | string or null | arXiv id when known                                                                                                                           |
| `embedding_similarity` | float          | Cosine similarity between`sub_question` and `abstract` with `BAAI/bge-base-en-v1.5` (used for sampling; also a useful baseline feature) |
| `relevant`             | bool           | **Gold label**                                                                                                                          |
| `label_confidence`     | float          | Annotator's certainty in the label, 0-1 (not the probability of relevance)                                                                    |
| `label_reason`         | string         | One-line justification for the label                                                                                                          |
| `label_source`         | string         | `claude-manual` (see below)                                                                                                                 |
| `quality_flag`         | string or null | Set for the few records with metadata problems (see "Known issues")                                                                           |

Example (abstract shortened):

```json
{{example_json}}
```

`metadata/sub_questions.json` lists the 30 sub-questions with their detail questions (the detail questions were only used to generate search
queries, not for labeling).

## How the data was built

1. **Sub-questions.** 30 technical questions written by hand across ML/NLP, systems, vision, privacy and security, RL and speech.
2. **Retrieval.** For each question, search queries were generated with an LLM and run through arXiv, Semantic Scholar, IEEE Xplore and OpenAlex
   (OpenAlex with both an AI-reranked keyword search and a semantic search); results were merged and de-duplicated. Only papers with an abstract
   longer than 200 characters were kept.
3. **Sampling.** 12 papers per question were sampled from the top, middle and lower thirds of the similarity-ranked pool (42% / 33% / 25%, seed 42),
   so the benchmark contains borderline papers and hard negatives rather than only obvious positives.

## How the labels were made

Every title and abstract was read and labeled **by hand by Claude (an LLM), in batches, against the sub-question's main topic only**, seeing exactly the
text a judge model sees. It is a single annotator and has **not** been verified by human experts.

- **Relevant** if the paper would be cited as direct evidence or a core reference for the question: it studies, proposes, evaluates or surveys the
  specific problem, method or phenomenon the question names.
- **Not relevant** if it only shares keywords or the broad field, is off-domain, uses the topic as a minor ingredient of a different problem, or is
  an adjacent method (for example reward-model length bias on an LLM-as-a-judge question, tensor-parallel *inference* on a distributed *training*
  question, or Whisper-based ASR on a *self-supervised* ASR question).
- `label_confidence`: 0.95-0.99 unambiguous; 0.8-0.9 clear with a caveat; 0.6-0.75 borderline; 0.55-0.6 genuine coin-flips, flagged on purpose.
  {{n_low_conf}} rows have confidence below 0.7, and these are the most contestable labels.

## Statistics

- **{{n_relevant}} relevant / {{n_not_relevant}} not relevant.** Always answering "relevant" gives **{{majority_acc}}%** accuracy.
- Relevant papers per question range from {{min_rel_per_q}} to {{max_rel_per_q}}.

Relevant rate by retrieval source:

{{source_table}}

Relevant rate by `embedding_similarity` band:

{{sim_table}}

### Baselines to beat

- Majority class ("always relevant"): **{{majority_acc}}%** accuracy.
- A single `embedding_similarity` threshold: **{{best_acc}}%** accuracy at {{best_thr}}. The best threshold was chosen on this same data, so treat that number as slightly optimistic.
- The threshold used in TRACE's embedding pre-filter, 0.56: **{{prod_acc}}%** accuracy. It keeps {{prod_recall}}% of the relevant papers but also lets through
  {{prod_kept_irrelevant}} of the {{n_irrelevant}} irrelevant ones, which is the gap an LLM judge is meant to close. Compare models on the hard middle band
  (similarity 0.6-0.8) as well as overall.

## Intended use

- Comparing small LLMs, prompts and heuristics as abstract-relevance judges (accuracy, precision/recall/F1, calibration, JSON-validity, latency).
- Choosing a confidence threshold for a screening step.

**Out of scope:** training a production model on it (too small and single-annotator), judging relevance from full text, or treating small
accuracy differences as significant (with {{n_rows}} rows the 95% interval on one accuracy number is about +/-5 points, and rows within a question
are correlated).

## Limitations and biases

- **Single LLM annotator**, no inter-annotator agreement; systematic bias in how strictly "adjacent method" is judged is possible.
- Relevance is judged against the **main topic only**; a paper relevant to a detail question but not the main topic is labeled not relevant.
- **Source and time skew:** mostly OpenAlex and arXiv, about two thirds from 2023-2026. IEEE-style journal abstracts are absent (the IEEE API returned
  no results during collection), so accuracy here may overstate accuracy on such sources.
- **Class balance** is {{pct_relevant}}% relevant, because modern search returns mostly on-topic papers; report precision/recall/F1, not accuracy alone.
- Only technical computer-science topics are covered.

## Known issues (`quality_flag`)

{{flag_table}}

Filter these out (`quality_flag` is not null) if you need clean title/abstract pairs. They were labeled on the best reading of the title and the
visible text, with reduced confidence.

## Licensing and attribution

- The **annotations** (`relevant`, `label_confidence`, `label_reason`, the sampling and the structure) are released under **{{license}}**.
- The **titles and abstracts** are bibliographic metadata retrieved from OpenAlex (CC0), arXiv (metadata released under CC0) and, for
  {{n_s2}} rows, Semantic Scholar (subject to Semantic Scholar's own terms). Copyright in each abstract remains with its authors or publisher; they are
  included here only as short evaluation text. If you are a rights holder and want a record removed, please open an issue in the GitHub repository.

## Citation

```bibtex
@misc{trace_relevance_judge_2026,
  title        = {TRACE Relevance Judge Benchmark},
  author       = {Lakshya Varshney},
  year         = {2026},
  howpublished = {Hugging Face Datasets},
  note         = {Source code: https://github.com/minorproject1research-coder/TRACE/tree/main/evaluation/relevance_judge}
}
```
