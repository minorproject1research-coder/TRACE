# Base model test for the query generator (planner): what the fine-tuning added

Date of the analysis: 2026-11-17. The answers were generated on the model host (`mllab`, RTX 2000 Ada 16 GB) with a vLLM server; the scoring and the extra analysis were run on the development laptop (CPU).
Notebook: `training/question_generator/base_model_eval.ipynb` (the first, generating run is saved as `base_model_eval_base.ipynb`, the re-scoring run as `base_model_eval.ipynb`).
Extra analysis: `training/question_generator/analyze_base_run.py`. Saved answers: `training/question_generator/eval_checkpoint_Qwen3.5-9B-Base_0shot.jsonl`.

## 0. Summary (for the slides)

**Question.** The planner is `Qwen/Qwen3.5-9B-Base` fine-tuned with LoRA on question-decomposition examples. What does the fine-tuning add, compared with the same model before fine-tuning?

**Test.** The same 4,821 held-out questions, the same system prompt, the same sampling settings (temperature 0.3, top-p 0.9, at most 768 new tokens) and the same metric code as the fine-tuned model's test in `training/question_generator/model.ipynb`. The base model gets no examples (zero-shot).

- **Format: the base model cannot be used as it is.** None of its 4,821 answers is valid JSON (0.0%). It answers in markdown. The fine-tuned model writes valid JSON in 99.6% of the answers (4,801 of 4,821). The pipeline needs JSON, so this is the clearest effect of the fine-tuning. The prompt does not ask for JSON, so the format is learned in the fine-tuning, not followed from an instruction.
- **Content: the base model is behind, most on the topics.** After the plan is read out of the markdown, its similarity to the reference plan is 0.665 for topics (fine-tuned 0.901), 0.804 for detail questions (0.838) and 0.744 for search queries (0.894).
- **How big these gaps are.** Two unrelated plans already score about 0.48 to 0.50 with this metric (section 4.2). Counted from that floor, the base model covers about 43% of the way to the fine-tuned model on topics, about 90% on details and about 64% on queries.
- **Counts: the base model writes more than the reference.** It writes 5.9 topics and 18.2 detail questions per plan, where the reference has 3.9 and 10.3. It gets the number of topics right in 17.7% of the answers (fine-tuned 45.2%).
- **Part of the topic gap is wording.** The reference topics are full questions (99.8% end with "?", 11 words on average). The base model's topics are short headings (3.7% are questions, 4 words on average). This was not tested as a cause, but it points in that direction (section 4.4).

**What this does not show.** It does not show that the base model could not be made to write the plan with examples in the prompt (few-shot), or with a prompt that asks for JSON. Neither was tested. It also does not show which plan is better for the research: the score measures resemblance to one reference plan.

## 1. What was tested

| | Base model (this test) | Fine-tuned model (`model.ipynb`, cells 45 to 50) |
|---|---|---|
| Weights | `Qwen/Qwen3.5-9B-Base`, no adapter | the same, plus the LoRA adapter (`checkpoint-32538`) |
| How it ran | vLLM server on the host, model name `base`, `max_model_len` 4096, 16 requests at once; weights in fp8 (set in `docker-compose.base-model-test.yml`, the notebook output shows only the name and the length) | Unsloth, 4-bit, one answer at a time |
| Questions | the 4,821 rows of `test.jsonl` | the same file |
| Prompt | the system prompt of the training data; the prompt of `model.ipynb` cell 47 (the chat template plus an empty think block, which makes the think tag appear twice); no examples | the same prompt |
| Sampling | temperature 0.3, top-p 0.9, 768 new tokens, a different seed for each request | the same settings |
| Metric | cosine similarity of `BAAI/bge-base-en-v1.5` embeddings (on the CPU), topic, details and queries as joined text; count match | the same code |

Two differences to state: the base model was served in fp8 by vLLM and the fine-tuned model was run in 4 bit, and the sampling is done by two different programs. Both use the same temperature and top-p.

Average cost of the base model: 43.4 s per answer (with 16 requests at once), 716 new tokens on average.

## 2. Results

### 2.1 Two scores for the base model

- **Strict score.** The answer must be valid JSON, as in `model.ipynb`. A markdown answer scores 0. It says whether the pipeline could use the model as it is.
- **Lenient score.** A reader (`parse_markdown_plan` in the notebook) turns the markdown into the same structure (topics, detail questions, search queries), and the same metrics are applied. It measures the content of the plan, independent of the format. The reader is a heuristic. The raw answers are saved, so the scores can be recomputed.

### 2.2 The table (all 4,821 questions)

| | Base, strict | Base, lenient | Fine-tuned |
|---|---|---|---|
| Valid JSON, or a plan could be read | 0.0% | 99.0% | 99.6% |
| Plan with topics and search queries | 0.0% | 90.8% | 99.6% |
| Topic similarity (answers read only) | 0 | 0.665 | 0.901 |
| Details similarity (answers read only) | 0 | 0.804 | 0.838 |
| Query similarity (answers read only) | 0 | 0.744 | 0.894 |
| Topic similarity (all rows, unread = 0) | 0 | 0.658 | 0.897 |
| Details similarity (all rows, unread = 0) | 0 | 0.796 | 0.835 |
| Query similarity (all rows, unread = 0) | 0 | 0.737 | 0.890 |
| Topic count equals the reference | 0.0% | 17.7% | 45.2% |
| Query count equals the reference | 0.0% | 6.3% | 10.6% |

The fine-tuned numbers are those of its own test on the same 4,821 questions. For the base model, 4,773 of 4,821 answers could be read (48 could not), 2,868 answers (59.5%) were cut off at the 768-token limit, and none was valid JSON ("no JSON at all": 4,821 of 4,821).

## 3. How to read the numbers

- **Valid JSON** answers the question "can TRACE use the model": the planner's output goes straight into the pipeline.
- **Similarity** compares the text of the model's topics, details and queries with the reference's. A score near 1 means very similar wording and subject. It is a coarse measure, and a different good plan scores lower.
- **Count match** is the share of answers with exactly the reference's number of topics (or queries). It is strict, and for the base model it also depends on how the reader splits the markdown. Quote the similarity scores before the count rates.
- **Floor.** The metric does not start at 0: two plans for different questions already look somewhat alike. Section 4.2 measures that floor.

## 4. Findings

### 4.1 The format comes from the fine-tuning

The base model never wrote JSON. The first answers show the usual form: `**Research Question:** ...`, then `**Decomposed Sub-Questions:**`, topic headings in bold and bullet lists, sometimes "Search Query: ..." lines. 90.8% of the answers have both topics and queries after reading.

The system prompt says to break the question into topic-grouped sub-questions with detail questions and to provide search-ready queries. It does not mention JSON. The 0% therefore means that the output format is something the fine-tuning teaches, not something the base model ignored. Whether the base model writes JSON when it is asked to, or when it sees examples, was not tested.

### 4.2 Content: how far above the floor

On a random sample of 600 readable answers (seed 42), the base model's answers were also scored against the reference of **another** question, as a floor:

| | Own reference | Another question's reference (floor) |
|---|---|---|
| Topics | 0.666 | 0.484 |
| Details | 0.810 | 0.502 |
| Queries | 0.751 | 0.483 |

The sample's numbers (0.666, 0.810, 0.751) agree with those of the full set (0.665, 0.804, 0.744). Placing the full-set numbers between the floor and the fine-tuned model (the floor is measured on the base model's answers and assumed to be about the same for the fine-tuned model):

| | Floor | Base | Fine-tuned | Base's share of the distance |
|---|---|---|---|---|
| Topics | 0.484 | 0.665 | 0.901 | about 43% |
| Details | 0.502 | 0.804 | 0.838 | about 90% |
| Queries | 0.483 | 0.744 | 0.894 | about 64% |

So the base model is clearly above the floor on all three. The detail questions are nearly as close to the reference as the fine-tuned model's. The topics are the weak part. Read the second half of the table as a rough picture: it rests on one assumed floor.

### 4.3 Counts

For the answers that were read (4,773):

| | Base model writes | Reference has |
|---|---|---|
| Topics per plan | 5.87 | 3.91 |
| Detail questions per plan | 18.2 | 10.3 |
| Search queries per plan | 13.99 | 12.73 |

75.4% of the base answers have 4 to 6 topics, while 78.3% of the references have 3 or 4. The base model has its own habit (five topics is the most common, 1,751 answers), the reference follows the question. 394 of the readable answers have no search queries at all, which is why only 90.8% of all answers have both.

### 4.4 Topics: the reference writes questions, the base model writes headings

| | Reference topics | Topics read from the base answers |
|---|---|---|
| Number | 18,858 | 28,037 |
| End with "?" | 99.8% | 3.7% |
| Words on average | 11.1 | 4.4 |

A reference topic looks like "What are the factors that can cause an ecosystem to become unstable?". A base-model topic looks like "Key Drivers of Instability". The embedding of a short heading and a full question differ, so a part of the topic gap (0.665 against 0.901) is probably the form of the topic, not the subject. The detail questions, which are questions on both sides, are much closer (0.804 against 0.838), which fits this. The test does not separate the two causes. The prompt does not tell the base model to write topics as questions.

### 4.5 Cut-off answers

59.5% of the base answers (2,868) reached the 768-token limit, because the base model writes long answers (median 768 tokens, mean 716). One would expect the cut answers to score lower. On the 600-answer sample they do not:

| | Cut at the limit (364 answers) | Finished (236 answers) |
|---|---|---|
| Topic similarity | 0.672 | 0.658 |
| Details similarity | 0.814 | 0.805 |
| Query similarity | 0.755 | 0.744 |

The similarity scores do not depend on the cut. The count matches do, on all 4,773 readable answers: the topic count matches in 14.3% of the cut answers and in 22.7% of the finished ones. The limit is the same in both tests (768 tokens), as in `model.ipynb`. How many of the fine-tuned model's answers were cut off was not checked here.

## 5. Limits of this test

- **Zero-shot only.** No examples in the prompt, and a prompt that does not ask for JSON. A base model with a few examples may write the format. This is the main thing that was not tested.
- **One reference per question.** The score measures resemblance to the reference plan of the dataset, not the quality of the plan for the research. Another sensible plan scores lower.
- **The reader is a heuristic.** 48 answers could not be read at all. The topic and detail split of markdown is the reader's decision (a bold heading is a topic, a bullet under it a detail), and it changes the numbers. An earlier version of the reader gave 0.690 / 0.727 for topics and details and 13.7% for the topic count (these are also the lenient numbers printed in `base_model_eval_base.ipynb`; the results file that run wrote was removed because it held only these older numbers); the numbers in this document are those of the final reader (self-tested on five markdown styles) and of the `_new.json` results file. The query numbers were the same in both versions.
- **The prompt is the one of `model.ipynb`.** It ends with a doubled think tag, which the training examples do not have. `CLEAN_THINK_PROMPT = True` in the notebook gives the single empty block. It was not run.
- **Two serving setups.** fp8 in vLLM for the base model, 4 bit in Unsloth for the fine-tuned model.
- **One run, one seed.** No repeated runs and no confidence interval, so there is no estimate of the variation between runs.
- **The floor** is measured for the base model's answers on 600 answers, and assumed to hold for the fine-tuned model.

## 6. Files and how to reproduce

| File | What it is |
|---|---|
| `training/question_generator/base_model_eval.ipynb` | the notebook; `SCORE_ONLY = True` re-scores the saved answers with no server and no GPU |
| `training/question_generator/base_model_eval_base.ipynb` | the first run on the host, which generated the answers (with the first version of the reader) |
| `training/question_generator/eval_checkpoint_Qwen3.5-9B-Base_0shot.jsonl` | the 4,821 saved answers, one line each, with the reference, time and token count (28 MB) |
| `training/question_generator/eval_results_Qwen3.5-9B-Base_0shot_new.json` | **the final results file** (59 MB): settings, strict and lenient summaries, and every answer with its scores. Written by the last cell of `base_model_eval.ipynb` after the re-score. Its summaries are the numbers of section 2.2 (for example topic similarity 0.6649, details 0.8039, query 0.7439, topic count match 17.7%) |
| `training/question_generator/docker-compose.base-model-test.yml` | the vLLM server for the base model |
| `training/question_generator/analyze_base_run.py` | the extra analysis of sections 4.2 to 4.5 (about 5 minutes on a laptop CPU) |

To reproduce: `python analyze_base_run.py` in `training/question_generator/` (needs the checkpoint file and `bge-base-en-v1.5`). Its first part prints the counts without a model; the second scores a random sample of 600 answers with a floor. A test of the script on 100 answers gave the same counts as the notebook and a floor of 0.494 / 0.507 / 0.483.

To run the test again from the start: start the server with the compose file, set `SCORE_ONLY = False` and run the notebook. The answers already in the checkpoint file are not generated again.
