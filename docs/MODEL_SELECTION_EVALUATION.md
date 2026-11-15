# Model selection evaluation: the embedding model and the NLI model

Date of the tests: 2026-11-15 and 2026-11-16. Everything was run on the development laptop (Intel Core Ultra 7 155H, 16 threads, no GPU), without Groq and without the pipeline.
Scripts: `evaluation/model_selection/` (`eval_embeddings.py`, `eval_nli.py`, `summarize.py`). Raw results: `evaluation/model_selection/results/`.

## 0. Summary (for the slides)

**Embedding model (`BAAI/bge-base-en-v1.5`).**
- It was chosen before any test. These tests were done afterwards, against five other models, one prompt variant of bge-base itself and a word-matching baseline (BM25).
- The model is a **good and defensible choice, but not the best one on every task**. It is in the top group on all three tasks. It clearly beats the small general-purpose models (`all-MiniLM-L6-v2`, `all-mpnet-base-v2`).
- Two base-size models beat it on one task each: `e5-base-v2` at ranking abstracts for a sub-question (AUC 0.915 against 0.880) and `gte-base` at finding the abstract for a scientific claim (nDCG@10 0.762 against 0.738).
- `bge-small` is statistically tied with it on both and 2.2 times faster.
- Changing the model would also mean re-tuning thresholds that were set on bge-base's similarity scale. No tested model is clearly better on everything, so we keep it.

**NLI model (`DeBERTa-v3-large-mnli-fever-anli-ling-wanli`).**
- It is the best of five models on every test set, and the gap grows on scientific text. On whole abstracts it reaches 0.756 three-way accuracy, against 0.693 for the base size and 0.44 to 0.49 for the two small models.
- On the real quote-to-claim pairs of the demonstration run, the smaller models lose 23% to 39% of the supports the large model finds.
- The large model found all 9 true conflicts of Stage 4's labelled set. The smaller models found 4 to 7.

**A finding about the pipeline.** The NLI model is stored in half precision (float16), and the library loads it that way, which the CPU runs very slowly. In float32 it gives the same decisions about 10 times faster on real pairs. This is not fixed in the pipeline yet (section 4.4).

## 1. How to read this document

- **What "tested" means here.** Each model gets the same data and the same metrics. The data are either public sets with human labels or TRACE's own labelled sets. The settings (thresholds, prefixes, input format) are the ones the pipeline uses.
- **AUC** is the chance that a model scores a random relevant item above a random irrelevant one (0.5 is chance, 1.0 is perfect). It does not depend on a threshold.
- **nDCG@10** is how high the correct abstracts are ranked in the top 10 (1.0 is perfect).
- **Confidence intervals** are 95% bootstrap intervals. When two models differ by less than the width of the interval, the data cannot tell which is better. Paired differences against bge-base are given as well.
- **Honesty note.** The embedding model was picked for its reputation and size, and no comparison was made at the time. The tests below are therefore a check after the fact. They could have shown the choice to be bad. They did not, but they also do not show it to be the best.

## 2. The embedding model

### 2.1 Where TRACE uses it

One shared model (`get_embedder()`), no query instruction, cosine of normalised vectors:
- Stage 1: remove sub-questions that repeat each other and rank search queries.
- Stage 2: the pre-filter, which scores each abstract against the sub-question (minimum similarity 0.56) before the LLM judge.
- Stage 3: choose the chunks of a paper that are shown to the digest model, and check coverage of the aspects.
- Stage 4: group claims that say the same thing, and find the quotes that contradict a claim (topic gate at cosine 0.70).
- Stage 5: choose which findings answer each part of the question.

### 2.2 Candidates

| Model | Size | Why it is a candidate |
|---|---|---|
| `bge-base-en-v1.5` (TRACE) | 110M parameters, 768 dimensions | the current choice |
| `bge-base-en-v1.5` + query instruction | same | the retrieval prompt recommended on its model card, which TRACE does not use |
| `bge-small-en-v1.5` | 33M, 384 | same family, a third of the size |
| `all-MiniLM-L6-v2` | 23M, 384 | a very common small default |
| `all-mpnet-base-v2` | 110M, 768 | a common base-size default |
| `e5-base-v2` | 110M, 768 | another base-size retrieval model |
| `gte-base` | 110M, 768 | another base-size retrieval model |
| BM25 | no model | a word-matching floor: what do embeddings add? |

Not tested: `bge-large-en-v1.5` and `e5-large-v2`. The test run was stopped twice because the laptop ran out of memory. A partial log of `e5-large-v2` showed a Stage 2 AUC of 0.923 and a speed about three times slower than bge-base. That check is not in the tables and is not a result.

### 2.3 Tests

| Test | Data | What it measures |
|---|---|---|
| T1 Stage 2 pre-filter | 360 papers labelled relevant or not to their sub-question (`evaluation/relevance_judge`; 237 relevant, 123 not; labels by one LLM annotator, not a human) | how well the similarity separates relevant from irrelevant abstracts |
| T2 claim to abstract | SciFact (BEIR test split), 300 scientific claims, 5,183 abstracts, human-labelled, public | finding the paper that backs a claim, the nearest public task to Stages 3 and 4 |
| T3 TRACE's own data | the 165 claims and 173 quotes of run `9b56d11b`; the 30 claim pairs labelled "same claim or not" in `reports/stage4_eval_set.json` | whether a claim finds the quote it was written from; whether paraphrases are close |
| T4 cost | 96 abstracts on this CPU | speed, size, memory |

**Check of the test setup.** The BM25 baseline gets 0.664 on SciFact (the BEIR paper reports 0.665). `bge-base` with the query instruction gets 0.740, `gte-base` 0.762 and `e5-base-v2` 0.719, which are the figures on their model cards. So the code measures what the literature measures.

### 2.4 Results

**Table E1: Stage 2 pre-filter (T1, 360 papers).**

| Model | AUC (95% interval) | Mean AUC inside a question | nDCG@5 | Irrelevant papers let through at 95% recall |
|---|---|---|---|---|
| e5-base-v2 | 0.915 (0.888 to 0.942) | 0.923 | 0.953 | 43% |
| bge-base + query instruction | 0.899 (0.865 to 0.930) | 0.881 | 0.927 | 50% |
| bge-small | 0.884 (0.849 to 0.920) | 0.868 | 0.917 | 42% |
| **bge-base (TRACE)** | **0.880 (0.842 to 0.915)** | 0.867 | 0.911 | 50% |
| gte-base | 0.877 (0.837 to 0.912) | 0.862 | 0.903 | 51% |
| all-MiniLM-L6-v2 | 0.860 (0.821 to 0.899) | 0.828 | 0.894 | 56% |
| all-mpnet-base-v2 | 0.855 (0.816 to 0.890) | 0.859 | 0.921 | 51% |
| BM25 (no model) | 0.802 | 0.856 | | |

Paired difference against bge-base: e5-base +0.035 (+0.008 to +0.063, reliable); bge-base with instruction +0.019 (+0.001 to +0.038, borderline); bge-small +0.004 and gte-base -0.003 (no difference); MiniLM -0.020 and mpnet -0.025 (intervals contain 0).

**Table E2: scientific claim to abstract (T2, SciFact, 300 claims, 5,183 abstracts).**

| Model | nDCG@10 (95% interval) | Recall@10 | Recall@100 |
|---|---|---|---|
| gte-base | 0.762 (0.722 to 0.800) | 0.890 | 0.968 |
| bge-base + query instruction | 0.740 (0.701 to 0.779) | 0.874 | 0.967 |
| **bge-base (TRACE)** | **0.738 (0.695 to 0.776)** | 0.866 | 0.970 |
| bge-small | 0.720 (0.677 to 0.758) | 0.845 | 0.953 |
| e5-base-v2 | 0.719 (0.678 to 0.761) | 0.846 | 0.963 |
| all-mpnet-base-v2 | 0.656 (0.606 to 0.701) | 0.790 | 0.942 |
| all-MiniLM-L6-v2 | 0.645 (0.596 to 0.691) | 0.783 | 0.925 |
| BM25 (no model) | 0.664 | | |

Paired difference against bge-base: gte-base +0.024 (+0.005 to +0.046, reliable); instruction +0.003, bge-small -0.018 and e5-base -0.018 (no reliable difference); mpnet -0.082 and MiniLM -0.093 (reliably worse, and no better than BM25).

**Table E3: TRACE's own data (T3).**

| Model | A claim finds its own quote: top 1 | top 5 | MRR | Same-claim pairs: AUC (30 pairs) |
|---|---|---|---|---|
| bge-base + query instruction | 0.594 | 0.770 | 0.683 | 0.619 |
| **bge-base (TRACE)** | **0.594** | 0.721 | 0.661 | 0.540 |
| e5-base-v2 | 0.545 | 0.745 | 0.649 | 0.778 |
| gte-base | 0.564 | 0.715 | 0.643 | 0.571 |
| bge-small | 0.467 | 0.655 | 0.555 | 0.667 |
| all-MiniLM-L6-v2 | 0.461 | 0.600 | 0.539 | 0.598 |
| all-mpnet-base-v2 | 0.382 | 0.533 | 0.465 | 0.635 |

**Table E4: cost on this laptop (CPU only, speed measured again on the idle machine).**

| Model | Parameters | Dimensions | Max tokens | Size on disk | Abstracts per second |
|---|---|---|---|---|---|
| all-MiniLM-L6-v2 | 23M | 384 | 256 | 183 MB | 48.5 |
| bge-small | 33M | 384 | 512 | 135 MB | 18.9 |
| **bge-base (TRACE)**, e5-base, gte-base, mpnet | 110M | 768 | 512 (mpnet 384) | 439 MB (gte 220 MB) | 8.4 to 8.7 |

### 2.5 What the results say

1. **bge-base is in the top group on every task and never the worst.** It is first on the in-domain test T3 (top 1: 0.594, tied with the instructed variant). It is far ahead of MiniLM and mpnet on SciFact and on T3.
2. **It is not the best.** `e5-base-v2` is reliably better at the Stage 2 pre-filter, and `gte-base` is reliably better on SciFact. Neither wins the other task or T3. The same-size models cost the same time, so there is no speed argument for bge-base over them.
3. **A smaller model is a real alternative.** `bge-small` is statistically tied with bge-base on T1 and T2 and runs 2.2 times faster. T3 is its weak spot (top 1: 0.467 against 0.594).
4. **The query instruction helps a little at Stage 2** (+0.019 AUC) and not on SciFact. TRACE does not use it.
5. **Embeddings do add something over words.** On SciFact the base-size retrieval models score 0.72 to 0.76 against 0.664 for BM25. On T1 the gap is smaller (0.88 against 0.80), and the best embedding model still lets 42% to 50% of the irrelevant papers through when 95% of the relevant ones are kept. This is why Stage 2 has an LLM judge after the pre-filter.
6. **Why we keep bge-base.** Several thresholds were set on its similarity scale (the 0.56 pre-filter, the 0.70 topic gate and near-match gates of Stage 4, the 0.3 relevance minimum of Stage 5), and the Stage 3 chunk cache is keyed to the model. Switching to e5 or gte would need all of them re-tuned and every cache rebuilt, for a gain on one task each. The tests do not justify that. If the thresholds are ever re-tuned, `e5-base-v2` (Stage 2) and `gte-base` (claim retrieval) are the two models to try first.

### 2.6 Limits of the embedding tests

- **T1 labels** come from one LLM annotator, not from people. The 360 papers were sampled from similarity bands of bge-base itself, to include borderline cases. The mix is not the mix of a real run. With 360 rows an AUC difference below about 0.03 cannot be told apart.
- **T3 is easy and partly circular:** the claims were written from the quotes, and both come from one run. The 30 same-claim pairs are too few for a ranking (their AUC values are shown but should not be used to choose a model).
- **SciFact is biomedical.** TRACE questions are mostly computer science. It is the best public test of the task, but it is not the same field.
- **Large models are not covered** (section 2.2). Only one question was used for the in-domain tests. The effect of the embedding model on the final report was not tested.
- **Speeds** come from one laptop CPU. A GPU would change the ratios.

## 3. The NLI model

### 3.1 Where TRACE uses it

`MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli` (435M parameters, 1.7 GB). Thresholds are those of the code.
- **Support** (Stage 4, and Stage 5 for every written sentence): the quote entails the claim with probability at least 0.50.
- **Conflict prefilter** (Stage 4): another document's quote contradicts the claim with probability at least 0.70. A judge decides afterwards, so missing a conflict matters most here.

### 3.2 Candidates

| Model | Parameters | Role in the comparison |
|---|---|---|
| DeBERTa-v3-large (TRACE) | 435M | the current choice |
| DeBERTa-v3-base (MoritzLaurer, trained on MNLI, FEVER and ANLI) | 184M | the next size down, same family |
| DeBERTa-v3-xsmall (cross-encoder) | 71M | a small model |
| MiniLM2-L6-H768 (cross-encoder) | 82M | a small model of another family |
| BART-large-mnli (Facebook) | 407M | a large model of another family, about the same size |

All models were loaded in float32 (section 4.5 explains why).

### 3.3 Tests

| Test | Data | Gold labels |
|---|---|---|
| N1a SciFact rationales | 773 pairs: the evidence sentences of an abstract against a claim (508 support, 265 contradict) | human; same shape as a quote against a claim |
| N1b SciFact abstracts | 450 pairs: the whole abstract against a claim; 150 each of support, contradict, not enough information (seed 42) | human |
| N2 SciTail | 2,126 pairs from science questions | entailment or not, from the dataset |
| N3 MNLI | 1,000 pairs from the validation set, general language | the dataset; all models saw MNLI during training, so it is a sanity check |
| N4 TRACE sets | 16 support pairs and 41 conflict pairs (9 conflicts) of `reports/stage4_eval_set.json` | an LLM annotator, small |
| N5 real pairs | 221 quote-to-claim pairs of run `9b56d11b` | none: it shows only whether a model decides as the large model does |

### 3.4 Results

**Table N1: scientific claims against evidence (human labels).**

| Model | Support found (entailment >= 0.50 on SUPPORT) | False support (on CONTRADICT) | Conflict found (contradiction >= 0.70 on CONTRADICT) | False conflict | AUC, support against contradict | 3-way accuracy, whole abstracts |
|---|---|---|---|---|---|---|
| **DeBERTa-v3-large (TRACE)** | **0.522** | 0.030 | **0.721** | 0.033 | **0.947** | **0.756** |
| DeBERTa-v3-base | 0.433 | 0.045 | 0.630 | 0.043 | 0.910 | 0.693 |
| BART-large-mnli | 0.423 | 0.057 | 0.577 | 0.049 | 0.896 | 0.698 |
| DeBERTa-v3-xsmall | 0.293 | 0.038 | 0.577 | 0.065 | 0.881 | 0.489 |
| MiniLM2-L6-H768 | 0.272 | 0.042 | 0.377 | 0.030 | 0.852 | 0.436 |

**Table N2: other public sets.**

| Model | SciTail accuracy | SciTail F1 (entailment, 0.50) | SciTail AUC | MNLI accuracy |
|---|---|---|---|---|
| **DeBERTa-v3-large (TRACE)** | **0.871** | **0.833** | **0.936** | **0.913** |
| BART-large-mnli | 0.810 | 0.768 | 0.894 | 0.901 |
| DeBERTa-v3-base | 0.806 | 0.738 | 0.876 | 0.902 |
| DeBERTa-v3-xsmall | 0.785 | 0.717 | 0.854 | 0.861 |
| MiniLM2-L6-H768 | 0.780 | 0.704 | 0.855 | 0.856 |

**Table N3: TRACE's own labelled sets (small, LLM labels).**

| Model | Support set (16): precision / recall | Conflict set (41, 9 conflicts): conflicts found at 0.70 | Pairs flagged | False alarms |
|---|---|---|---|---|
| **DeBERTa-v3-large (TRACE)** | 0.833 / 0.625 | **9 of 9** | 13 | 4 |
| DeBERTa-v3-base | 1.000 / 0.625 | 7 of 9 | 12 | 5 |
| BART-large-mnli | 0.833 / 0.625 | 4 of 9 | 9 | 5 |
| DeBERTa-v3-xsmall | 1.000 / 0.875 | 4 of 9 | 6 | 2 |
| MiniLM2-L6-H768 | 1.000 / 0.750 | 4 of 9 | 5 | 1 |

**Table N4: agreement with the TRACE model on the 221 real quote-to-claim pairs (not accuracy).**

| Model | Same 3-way label | Same support decision | Supports of the large model that are lost | Supports added |
|---|---|---|---|---|
| DeBERTa-v3-base | 0.819 | 0.828 | 23 of 77 (30%) | 15 |
| BART-large-mnli | 0.882 | 0.887 | 18 of 77 (23%) | 7 |
| DeBERTa-v3-xsmall | 0.828 | 0.837 | 28 of 77 (36%) | 8 |
| MiniLM2-L6-H768 | 0.810 | 0.824 | 30 of 77 (39%) | 9 |

**Table N5: speed on this laptop's CPU (float32).**

| Model | Short pairs per second (SciTail) | Whole-abstract pairs per second | Parameters |
|---|---|---|---|
| DeBERTa-v3-large (TRACE) | 11.2 | 1.6 | 435M |
| BART-large-mnli | 11.6 | 1.4 | 407M |
| DeBERTa-v3-base | 39.3 | 5.0 | 184M |
| MiniLM2-L6-H768 | 100.5 | 13.3 | 82M |
| DeBERTa-v3-xsmall | 114.8 | 13.8 | 71M |

### 3.5 What the results say

1. **The large model is best on every set** (Tables N1 and N2). The gap to the smaller models grows with the difficulty: on general MNLI the five models are within 6 points (0.86 to 0.91), on SciTail within about 9 points, and on whole scientific abstracts the xsmall and MiniLM2 models fall to 0.44 to 0.49 against 0.756.
2. **Size alone does not explain the lead.** BART-large has about the same size as DeBERTa-large and is clearly worse on every public set (SciTail 0.810 against 0.871; abstracts 0.698 against 0.756). A likely reason is the model family and its training data (the large DeBERTa model was also trained on LingNLI and WANLI, the base model was not), but the tests do not separate these causes.
3. **The smaller models lose real supports** (Table N4): the base model loses 30% of the supports that the large model finds, and the small ones 36% to 39%. They also add some that the large model rejects. Fewer supports would mean more claims stay "unverified" in Stage 4 and fewer sentences pass the Stage 5 check.
4. **Conflicts** (Table N3): the large model found all 9 real conflicts of the labelled set and the base model 7 of 9. The others found 4. Because Stage 4 uses NLI only as a prefilter in front of a judge, a missed conflict is never seen again. This is the strongest reason for the large model, but the set is small (9 conflicts).
5. **The large model is strict.** On human-labelled SciFact rationales it accepts only 52% of true supports at 0.50, and falsely accepts 3% of the contradicting ones. It labels cautiously. This agrees with Stage 4's labels (111 of 165 claims in the demonstration run stay "unverified") but does not prove that this is the cause.
6. **Earlier tests agree.** Before these tests, a smaller experiment on 4 x 80 pairs of run 30 (`docs/reports/21_timings.md`) found that DeBERTa-base as a prefilter kept 7 of the 15 pairs the large model flags, and scored the pairs that the judge later called conflicts at 0.14, 0.17 and 0.00. Another note (`20_stage4.md`) found 9% label disagreement between base and large. The present tests repeat this on labelled data and add the other models.
7. **Cost.** The large model is 3 to 10 times slower than the smaller ones. With float32 it is fast enough (section 4), so there is no strong reason to give up its accuracy.

### 3.6 Limits of the NLI tests

- The TRACE sets (16 and 41 pairs) are small and labelled by an LLM annotator, not by people, and many conflict pairs were constructed. Table N4 has no gold labels.
- SciFact is biomedical, and in N1a the whole rationale is given, while TRACE gives one verbatim quote.
- All models were tested with the fixed thresholds of the code (0.50 and 0.70). A smaller model might do better with its own thresholds. This was not tried.
- The large model's support recall is only about half on human-labelled supports. A better model or fine-tuning on scientific claims could do more. We did not test models larger than DeBERTa-v3-large.

## 4. A finding about the pipeline: the NLI model is loaded in float16

### 4.1 What happens

`DeBERTa-v3-large-mnli-fever-anli-ling-wanli` and the base model are stored in half precision (float16). The installed version of the library (`transformers` 5.5.0) loads weights in the stored precision. This laptop's CPU has no fast float16 arithmetic, so the model runs about 10 times slower than in float32. The same happened to `gte-base` during these tests: it ran at 1.2 abstracts per second instead of 8.5, and Task Manager showed only about 11% processor use once during that slow stretch (a single observation).

### 4.2 Measurements

| Case | Float16 (as loaded now) | Float32 | Notes |
|---|---|---|---|
| DeBERTa-large on real quote-to-claim pairs | 0.92 pairs per second (100 pairs) | about 8.8 pairs per second (221 pairs in 25 s) | about 10 times faster |
| DeBERTa-large on 16 identical short pairs | 0.74 | 14.3 | a speed test only |
| `gte-base` embedding | 0.7 abstracts per second | 2.9 (8.5 on the idle machine) | |

On the 100 real pairs, float16 and float32 gave **the same 3-way label and the same support decision on every pair**. The largest difference in a probability was 0.008, and the mean difference 0.0002 (`results/fp16_vs_fp32_real_pairs.json`).

### 4.3 What it means

- Stage 4's NLI time was recorded as about 1.2 to 1.7 s per pair and 100 to 140 s per sub-question (`21_timings.md`), which fits the float16 speed. The notes concluded that nothing quality-neutral could make it faster. Loading in float32 is quality-neutral on these pairs, and the same NLI work would need roughly a tenth of the time (an estimate: 10 to 15 s instead of 100 to 140 s per sub-question).
- That would also make the cap of 80 pairs per sub-question and the "NLI on a GPU" item of the known limits much less important.

### 4.4 Status

Not changed in the pipeline. The fix is one argument where Stage 4 loads the model (`CrossEncoder(NLI_MODEL, model_kwargs={"torch_dtype": torch.float32})` in `apps/api/agents/stage4_factcheck/common.py`). Stage 4 belongs to the teammate, and the check above covers only 100 pairs of one run, so it should be confirmed on a stored run before it is made the default. The embedding model (bge-base) is stored in float32, so it is not affected.

### 4.5 Why the tests use float32

So that every model is measured at full speed and in the same way. The accuracy numbers do not depend on it (section 4.2). The speeds in Tables E4 and N5 are float32 speeds.

## 5. Files and how to repeat the tests

| File | Content |
|---|---|
| `evaluation/model_selection/eval_embeddings.py` | the embedding tests T1 to T4, the BM25 baseline, `--speed-only` for a clean speed pass |
| `evaluation/model_selection/eval_nli.py` | the NLI tests N1 to N5 |
| `evaluation/model_selection/summarize.py` | builds the tables (`results/summary.md`), paired intervals, published scores from the model cards |
| `evaluation/model_selection/results/` | one JSON file per model (all scores per row), `bm25.json`, `dtype_finding.json`, `fp16_vs_fp32_real_pairs.json`, run logs |

```
venv/Scripts/python.exe evaluation/model_selection/eval_embeddings.py     # about 1.5 hours for the models of this document (without the two large ones)
venv/Scripts/python.exe evaluation/model_selection/eval_nli.py            # about 25 minutes
venv/Scripts/python.exe evaluation/model_selection/summarize.py
```

The public data come from Hugging Face (`mteb/scifact`, `tasksource/scifact_entailment`, `allenai/scitail`, `nyu-mll/multi_nli`). The models come from their Hugging Face repositories. The TRACE data are `evaluation/relevance_judge/dataset.jsonl`, `reports/stage4_eval_set.json` and the evidence report of run `9b56d11b` (`reports/ppt_example/`, not in git). Without that last file T3 and N5 cannot be repeated.

## 6. Suggested wording for the report

> **Embedding model.** We use `bge-base-en-v1.5` for all similarity tasks. After the choice we compared it with five other embedding models, one prompt variant of the same model and a word-matching baseline on three tasks: ranking abstracts against a sub-question (360 labelled papers), retrieving the abstract that supports a scientific claim (SciFact, 300 claims, 5,183 abstracts) and matching claims to quotes in our own data. It was in the top group on all three tasks and clearly better than the two small general-purpose models. Two same-size models were better on one task each (`e5-base-v2` for ranking abstracts, `gte-base` for claim retrieval), and `bge-small` was tied on the first two and 2.2 times faster. As the thresholds of the pipeline were set on the similarity scale of bge-base, and no model was better on all tasks, we kept it.

> **NLI model.** We use `DeBERTa-v3-large-mnli-fever-anli-ling-wanli` for the support check and the conflict prefilter. We compared it with four other models (DeBERTa-v3-base, DeBERTa-v3-xsmall, MiniLM2-L6 and BART-large-mnli) on scientific claims with human labels (SciFact), science entailment (SciTail), general language (MNLI) and our own labelled pairs. It was best on every set. On whole scientific abstracts its three-way accuracy was 0.756, against 0.693 for the base size, and on real pairs of a pipeline run the smaller models lost 23% to 39% of the supports it finds. It also found all 9 conflicts of our labelled conflict set (the others found 4 to 7). The labelled sets are small and were labelled by a language model, which limits what can be concluded about the conflict check.
