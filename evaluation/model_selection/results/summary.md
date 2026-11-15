## Embedding models

### Table E1: Stage 2 pre-filter, 360 labelled papers (T1)

| Model | AUC (95% CI) | Average precision | Mean AUC inside a question | nDCG@5 | Irrelevant papers let through at 95% recall | Best-threshold accuracy |
|---|---|---|---|---|---|---|
| e5-base-v2 | 0.915 (0.888 to 0.942) | 0.954 | 0.923 | 0.953 | 43% | 0.844 |
| bge-base-en-v1.5 + query instruction | 0.899 (0.865 to 0.930) | 0.944 | 0.881 | 0.927 | 50% | 0.836 |
| bge-small-en-v1.5 | 0.884 (0.849 to 0.920) | 0.932 | 0.868 | 0.917 | 42% | 0.831 |
| bge-base-en-v1.5 **(TRACE)** | 0.880 (0.842 to 0.915) | 0.928 | 0.867 | 0.911 | 50% | 0.836 |
| gte-base | 0.877 (0.837 to 0.912) | 0.930 | 0.862 | 0.903 | 51% | 0.828 |
| all-MiniLM-L6-v2 | 0.860 (0.821 to 0.899) | 0.919 | 0.828 | 0.894 | 56% | 0.806 |
| all-mpnet-base-v2 | 0.855 (0.816 to 0.890) | 0.916 | 0.859 | 0.921 | 51% | 0.794 |
| BM25 (words only, no model) | 0.802 (rank-normalised per question) | | 0.856 | | | |

Paired difference of AUC against bge-base (same 360 rows, bootstrap 95% interval; an interval that contains 0 means no reliable difference):

- e5-base-v2: +0.035 (+0.008 to +0.063)
- bge-base-en-v1.5 + query instruction: +0.019 (+0.001 to +0.038)
- bge-small-en-v1.5: +0.004 (-0.019 to +0.027)
- gte-base: -0.003 (-0.024 to +0.018)
- all-MiniLM-L6-v2: -0.020 (-0.051 to +0.008)
- all-mpnet-base-v2: -0.025 (-0.063 to +0.010)

### Table E2: scientific claim to abstract retrieval, SciFact test (T2: 300 claims, 5,183 abstracts)

| Model | nDCG@10 (95% CI) | Recall@10 | Recall@100 | MRR@10 | Published nDCG@10 (model card) |
|---|---|---|---|---|---|
| gte-base | 0.762 (0.722 to 0.800) | 0.890 | 0.968 | 0.726 | 0.762 |
| bge-base-en-v1.5 + query instruction | 0.740 (0.701 to 0.779) | 0.874 | 0.967 | 0.703 | 0.740 |
| bge-base-en-v1.5 **(TRACE)** | 0.738 (0.695 to 0.776) | 0.866 | 0.970 | 0.700 |  |
| bge-small-en-v1.5 | 0.720 (0.677 to 0.758) | 0.845 | 0.953 | 0.684 |  |
| e5-base-v2 | 0.719 (0.678 to 0.761) | 0.846 | 0.963 | 0.684 | 0.719 |
| all-mpnet-base-v2 | 0.656 (0.606 to 0.701) | 0.790 | 0.942 | 0.618 |  |
| all-MiniLM-L6-v2 | 0.645 (0.596 to 0.691) | 0.783 | 0.925 | 0.605 |  |
| BM25 (words only, no model) | 0.664 | | | | 0.665 (BEIR paper) |

Paired difference of nDCG@10 against bge-base (same 300 claims):

- gte-base: +0.024 (+0.005 to +0.046)
- bge-base-en-v1.5 + query instruction: +0.003 (-0.016 to +0.021)
- bge-small-en-v1.5: -0.018 (-0.040 to +0.004)
- e5-base-v2: -0.018 (-0.041 to +0.005)
- all-mpnet-base-v2: -0.082 (-0.115 to -0.052)
- all-MiniLM-L6-v2: -0.093 (-0.126 to -0.061)

### Table E3: tasks on TRACE's own data (T3: 165 claims against 173 quotes of one run; 30 labelled claim pairs of Stage 4)

| Model | Claim finds its own quote: top 1 | top 5 | MRR | Same-claim pairs: AUC |
|---|---|---|---|---|
| bge-base-en-v1.5 + query instruction | 0.594 | 0.770 | 0.683 | 0.619 |
| bge-base-en-v1.5 **(TRACE)** | 0.594 | 0.721 | 0.661 | 0.540 |
| e5-base-v2 | 0.545 | 0.745 | 0.649 | 0.778 |
| gte-base | 0.564 | 0.715 | 0.643 | 0.571 |
| bge-small-en-v1.5 | 0.467 | 0.655 | 0.555 | 0.667 |
| all-MiniLM-L6-v2 | 0.461 | 0.600 | 0.539 | 0.598 |
| all-mpnet-base-v2 | 0.382 | 0.533 | 0.465 | 0.635 |

### Table E4: cost on this laptop (CPU only, Intel Core Ultra 7 155H, no GPU)

| Model | Parameters (M) | Dimensions | Max tokens | Size on disk (MB) | Abstracts per second | Load time (s) |
|---|---|---|---|---|---|---|
| all-MiniLM-L6-v2 | 22.7 | 384 | 256 | 183 | 48.51 | 6.9 |
| bge-small-en-v1.5 | 33.4 | 384 | 512 | 135 | 18.94 | 6.8 |
| all-mpnet-base-v2 | 109.5 | 768 | 384 | 439 | 8.35 | 5.8 |
| bge-base-en-v1.5 **(TRACE)** | 109.5 | 768 | 512 | 439 | 8.54 | 5.8 |
| bge-base-en-v1.5 + query instruction | 109.5 | 768 | 512 | 439 | 8.66 | 5.9 |
| e5-base-v2 | 109.5 | 768 | 512 | 439 | 8.56 | 5.8 |
| gte-base | 109.5 | 768 | 512 | 220 | 8.56 | 5.7 |

## NLI models

### Table N1: scientific claims against evidence (human labels)

SciFact rationales (N1a) have the same shape as the quote-to-claim pairs of TRACE. The thresholds are those of the code (support: entailment >= 0.50; conflict prefilter: contradiction >= 0.70).

| Model | Support found (SUPPORT with entailment >= 0.50) | False support (CONTRADICT with entailment >= 0.50) | Conflict found (CONTRADICT with contradiction >= 0.70) | False conflict | AUC support vs contradict | 3-way accuracy on whole abstracts (N1b) | Macro-F1 (N1b) |
|---|---|---|---|---|---|---|---|
| DeBERTa-v3-large (TRACE) **(TRACE)** | 0.522 | 0.030 | 0.721 | 0.033 | 0.947 | 0.756 | 0.757 |
| DeBERTa-v3-base | 0.433 | 0.045 | 0.630 | 0.043 | 0.910 | 0.693 | 0.693 |
| DeBERTa-v3-xsmall | 0.293 | 0.038 | 0.577 | 0.065 | 0.881 | 0.489 | 0.453 |
| MiniLM2-L6-H768 | 0.272 | 0.042 | 0.377 | 0.030 | 0.852 | 0.436 | 0.368 |
| BART-large-mnli | 0.423 | 0.057 | 0.577 | 0.049 | 0.896 | 0.698 | 0.699 |

### Table N2: other public sets

| Model | SciTail accuracy (entailment vs not, argmax) | SciTail F1 of entailment at 0.50 | SciTail AUC | MNLI matched accuracy (1,000) |
|---|---|---|---|---|
| DeBERTa-v3-large (TRACE) **(TRACE)** | 0.871 | 0.833 | 0.936 | 0.913 |
| DeBERTa-v3-base | 0.806 | 0.738 | 0.876 | 0.902 |
| DeBERTa-v3-xsmall | 0.785 | 0.717 | 0.854 | 0.861 |
| MiniLM2-L6-H768 | 0.780 | 0.704 | 0.855 | 0.856 |
| BART-large-mnli | 0.810 | 0.768 | 0.894 | 0.901 |

### Table N3: TRACE's own labelled pairs (small; labels by an LLM annotator)

| Model | Support set (16 pairs): precision / recall at 0.50 | Conflict set (41 pairs, 9 conflicts): conflicts found at 0.70 | Flagged | False alarms |
|---|---|---|---|---|
| DeBERTa-v3-large (TRACE) **(TRACE)** | 0.833 / 0.625 | 1.000 | 13 | 4 |
| DeBERTa-v3-base | 1.000 / 0.625 | 0.778 | 12 | 5 |
| DeBERTa-v3-xsmall | 1.000 / 0.875 | 0.444 | 6 | 2 |
| MiniLM2-L6-H768 | 1.000 / 0.750 | 0.444 | 5 | 1 |
| BART-large-mnli | 0.833 / 0.625 | 0.444 | 9 | 5 |

### Table N4: agreement with the TRACE model on the real quote-to-claim pairs of run 9b56d11b (no gold labels)

| Model | Pairs | Same 3-way label as the large model | Same support decision (entailment >= 0.50) | Supports the large model finds that this model loses | Supports this model adds |
|---|---|---|---|---|---|
| DeBERTa-v3-large (TRACE) | 221 | 1.000 | 1.000 | 0 of 77 | 0 |
| DeBERTa-v3-base | 221 | 0.819 | 0.828 | 23 of 77 | 15 |
| DeBERTa-v3-xsmall | 221 | 0.828 | 0.837 | 28 of 77 | 8 |
| MiniLM2-L6-H768 | 221 | 0.810 | 0.824 | 30 of 77 | 9 |
| BART-large-mnli | 221 | 0.882 | 0.887 | 18 of 77 | 7 |

### Table N5: cost on this laptop (CPU only)

| Model | Parameters (M) | Short pairs per second (SciTail) | Long pairs per second (whole abstracts) | Load time (s) |
|---|---|---|---|---|
| DeBERTa-v3-large (TRACE) **(TRACE)** | 435.1 | 11.19 | 1.58 | 11.2 |
| DeBERTa-v3-base | 184.4 | 39.28 | 5.03 | 10.2 |
| DeBERTa-v3-xsmall | 70.8 | 114.79 | 13.77 | 9.6 |
| MiniLM2-L6-H768 | 82.1 | 100.53 | 13.3 | 9.2 |
| BART-large-mnli | 407.3 | 11.61 | 1.36 | 10.3 |
