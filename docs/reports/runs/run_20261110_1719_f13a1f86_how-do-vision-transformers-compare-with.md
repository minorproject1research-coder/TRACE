# Pipeline run report - How do vision transformers compare with convolutional neural networks for image classification accuracy and data efficiency?

Generated 2026-11-10 18:04 by `scripts/pipeline_run_report.py` from `logs/pipeline.log` (run 34 in the file) and the database. Query id `f13a1f86-4ee0-423e-b90b-b790d5ad18bd`.

## 1. Summary

| | |
|---|---|
| Question | How do vision transformers compare with convolutional neural networks for image classification accuracy and data efficiency? |
| Domain anchor | 'deep learning' | context: Deep learning: vision transformers are neural network models, not electrical transformers. |
| Started / finished | 2026-11-10 17:19:26 / 17:41:07 |
| **Total execution time** | **21m 41s** (1301 s) |
| Sub-questions / search queries | 5 / 11 (per sub-question [3, 2, 2, 2, 2]) |
| Plan source | planner |
| Paper candidates retrieved (all sources), after the similarity floor, shortlisted | 446 candidates -> 442 cleared the similarity floor -> 100 shortlisted |
| **Papers kept after the relevance judge** | **58** (log: 55); 45 shortlisted papers rejected |
| **Web sources** | **50** (per sub-question [11, 10, 10, 10, 6]) |
| Papers attempted for parsing | 24 (top-N per sub-question) |
| **Papers parsed to usable full text** | **23** of 24 attempted (1 from the parse cache) |
| Papers not parsed (all routes failed) | 0 download/route failures + 0 database/parse error(s); the rest of the shortfall is abstract-only |
| PDF download attempts that failed | 12 (individual URL failures; most papers recovered through another route) |
| Stage 3 digests | 56 (38 from full text, 0 from abstracts, 18 from web snippets) |
| Findings (verified / total) | 172 / 190 |
| Coverage sufficient | 5 of 5 sub-questions |
| Judge | 3m 13s in 16 batches; model id `judge-v2` (from .env at report time) |
| Groq rate limiting | 275 parking events, 4416 key-seconds parked |

## 2. Time per phase

| Phase | Start | End | Duration | Share |
|---|---|---|---|---|
| Planner (decompose, 5 sub-questions) | 17:19:26 | 17:19:57 | 31s | 2% |
| Web search (Tavily) | 17:19:57 | 17:20:13 | 16s | 1% |
| Paper search (arXiv, IEEE, OpenAlex, Semantic Scholar, Scopus) | 17:20:13 | 17:20:45 | 32s | 2% |
| Embedding pre-filter + relevance judge | 17:20:45 | 17:21:37 | 52s | 4% |
| Citation enrichment (Semantic Scholar) | 17:21:37 | 17:21:48 | 11s | 1% |
| Store papers in the database | 17:21:48 | 17:21:49 | 1s | 0% |
| PDF download + Docling parsing | 17:21:49 | 17:28:16 | 6m 27s | 30% |
| Stage 3 preparation (aspect split, chunking, embedding) | 17:28:16 | 17:28:25 | 8s | 1% |
| Stage 3 digest generation (Groq) | 17:28:25 | 17:28:30 | 6s | 0% |
| Stage 3 judge + coverage (per sub-question) | 17:28:30 | 17:35:07 | 6m 37s | 31% |
| Stage 4 fact check (claims, NLI, judges) | 17:35:07 | 17:41:07 | 6m 00s | 28% |
| **Total** | 17:19:26 | 17:41:07 | **21m 41s** | 100% |

Loop 2 (second search for uncovered aspects) is part of the judge + coverage phase above: 8m 30s by its own step timings (39% of the run). Its searches, parses and filters are NOT counted in the retrieval figures of this report; it stored 3 new paper(s) and 3 new web page(s) with the run, so the stored counts of papers and web sources are higher than the log counts by these numbers.

## 3. Sub-questions: retrieval, filtering, parsing, Stage 3

| # | Sub-question | Pre-filter (cand. -> cleared -> shortlist) | Judge passed | Parsed full text | Web | Digests (full / abs / web) | Verified / total findings | Coverage |
|---|---|---|---|---|---|---|---|---|
| 1 | What are vision transformers (ViT)? | 110 -> 109 -> 20 | 9 of 20 | 5 | 11 | 8 (5 / 0 / 3) | 30 / 32 | sufficient |
| 2 | What are CNNs? | 93 -> 93 -> 20 | 18 of 20 | 5 | 10 | 11 (8 / 0 / 3) | 31 / 34 | sufficient |
| 3 | How is image classification accuracy measured and compared for different models? | 95 -> 95 -> 20 | 11 of 20 | 6 | 10 | 8 (5 / 0 / 3) | 28 / 31 | sufficient |
| 4 | How is data efficiency measured and compared for different models? | 85 -> 82 -> 20 | 3 of 20 | 6 | 13 | 15 (9 / 0 / 6) | 38 / 40 | sufficient |
| 5 | How do ViT and CNN compare in terms of image classification accuracy and data efficiency? | 63 -> 63 -> 20 | 14 of 20 | 6 | 6 | 14 (11 / 0 / 3) | 45 / 53 | sufficient |

- Relevance judge rejected 11 papers for [What are vision transformers (ViT)?]. Examples: 'Comparison of Vision Transformers and Convolutional Neural N' (The paper compares ViTs to CNNs in medical imaging rather than explaining what ViTs are.); 'DeepViT: Towards Deeper Vision Transformer' (The paper focuses on solving the 'attention collapse' problem in deep ViTs rather than explaining what ViTs are.); 'Vision Transformer Adapter for Dense Predictions' (The paper focuses on adapting ViTs for specific tasks rather than explaining what ViTs are.)
- Relevance judge rejected 2 papers for [What are CNNs?]. Examples: 'Are Convolutional Neural Networks or Transformers more like ' (The paper compares CNNs and Vision Transformers regarding human vision similarity rather than defining what CNNs are.); 'The Modern Mathematics of Deep Learning' (The paper discusses general mathematical analysis of deep learning rather than defining or explaining what CNNs are.)
- Relevance judge rejected 9 papers for [How is image classification accuracy mea]. Examples: 'Using image quality metrics to identify adversarial imagery ' (The paper focuses on detecting adversarial imagery using quality metrics rather than measuring or comparing classification accuracy across d); 'A study of accuracy variation from shallow to deep learning ' (The paper focuses on the impact of network depth on accuracy rather than the methodologies for measuring and comparing accuracy across diffe); 'Deep Learning Model of Image Classification Using Machine Le' (The paper focuses on proposing and optimizing a specific CNN model rather than explaining how to measure and compare accuracy across differe)
- Relevance judge rejected 17 papers for [How is data efficiency measured and comp]. Examples: 'Efficient Deep Learning: A Survey on Making Deep Learning Mo' (The paper focuses on general model efficiency (size, speed, resources) rather than specific metrics or methods for measuring and comparing d); 'Resource-Efficient Image Retrieval: A Study of Local Pattern' (The paper focuses on computational resource usage rather than specific data efficiency metrics or comparisons across different model archite); 'Introducing Image Classification Efficacies' (The paper focuses on general image classification efficacy metrics rather than data efficiency measurement or comparison across different de)
- Relevance judge rejected 6 papers for [How do ViT and CNN compare in terms of i]. Examples: 'Visualization Comparison of Vision Transformers and Convolut' (The paper focuses on visualization techniques and feature representation properties rather than comparing classification accuracy or data ef); 'Do Vision Transformers See Like Convolutional Neural Network' (The paper focuses on internal representation differences and architectural mechanisms rather than comparing classification accuracy or data ); 'Ensemble deep learning of CNN vs vision transformers for bra' (The paper focuses on ensemble techniques rather than a direct comparison of ViT and CNN data efficiency.)

### Sources behind each sub-question's digests

**1. What are vision transformers (ViT)?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Survey on Vision Transformer | paper | full_text | 4 / 5 |
| Comparing Vision Transformers and Convolutional Neural Networks for Image Classification: A Lit | paper | full_text | 3 / 4 |
| Do Vision Transformers See Like Convolutional Neural Networks? | paper | full_text | 5 / 5 |
| Vision Transformers Need Registers | paper | full_text | 5 / 5 |
| Vision Transformers vs. Convolutional Neural Networks: Benchmarking Across Tasks | paper | full_text | 5 / 5 |
| A Comparative Study of Convolutional Neural Networks and Vision Transformers for Agricultural I | web | web_snippet | 3 / 3 |
| A Comprehensive Study of Vision Transformers in Image Classification Tasks | web | web_snippet | 2 / 2 |
| Comparison of Vision Transformers and Convolutional Neural Networks in Medical Image Analysis:  | web | web_snippet | 3 / 3 |

**2. What are CNNs?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Layer-Wise Theoretical Framework for Deep Learning of Convolutional Neural Networks | paper | full_text | 3 / 4 |
| A Layer-Wise Theoretical Framework for Deep Learning of Convolutional Neural Networks | paper | full_text | 3 / 3 |
| A review of convolutional neural networks in computer vision | paper | full_text | 2 / 2 |
| A review of convolutional neural networks in computer vision | paper | full_text | 5 / 5 |
| Introduction to convolutional neural network using Keras; an understanding from a statistician | paper | full_text | 2 / 3 |
| On the Analyses of Medical Images Using Traditional Machine Learning Techniques and Convolution | paper | full_text | 2 / 2 |
| On the Analyses of Medical Images Using Traditional Machine Learning Techniques and Convolution | paper | full_text | 4 / 4 |
| Understanding of Convolutional Neural Network (CNN): A Review | paper | full_text | 2 / 3 |
| Comparison of Vision Transformers and Convolutional Neural Networks in Medical Image Analysis:  | web | web_snippet | 1 / 1 |
| Convolutional Neural Network - an overview | web | web_snippet | 4 / 4 |
| Convolutional neural networks: an overview and application in radiology | web | web_snippet | 3 / 3 |

**3. How is image classification accuracy measured and compared for different models?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Are we done with ImageNet? | paper | full_text | 5 / 5 |
| Image Classification With Small Datasets: Overview and Benchmark | paper | full_text | 5 / 5 |
| Introducing Image Classification Efficacies | paper | full_text | 3 / 4 |
| Klasifikasi Citra Menggunakan Convolutional Neural Network dan K Fold Cross Validation | paper | full_text | 4 / 5 |
| Performance Evaluation of Deep Learning Classification Network for Image Features | paper | full_text | 5 / 5 |
| (PDF) Performance Comparison of Deep Learning, Classical ML, and Large Language Models in Scala | web | web_snippet | 3 / 3 |
| Deep Learning Techniques for Image Classification / Computer Vision / Computer Vision and Multi | web | web_snippet | 2 / 2 |
| Saturating Image Classification Benchmarks - Convolutional Neural Networks - DeepLearning.AI | web | web_snippet | 1 / 2 |

**4. How is data efficiency measured and compared for different models?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| An Empirical Model of Large-Batch Training | paper | full_text | 4 / 4 |
| Data augmentation: A comprehensive survey of modern approaches | paper | full_text | 4 / 5 |
| Effective Evaluation of Deep Active Learning on Image Classification Tasks | paper | full_text | 5 / 5 |
| Effective Evaluation of Deep Active Learning on Image Classification Tasks | paper | full_text | 2 / 2 |
| Image Data Augmentation for Deep Learning: A Survey | paper | full_text | 3 / 3 |
| PePR: Performance Per Resource Unit as a Metric to Promote Small-Scale Deep Learning in Medical | paper | full_text | 4 / 5 |
| PePR: Performance Per Resource Unit as a Metric to Promote Small-Scale Deep Learning in Medical | paper | full_text | 2 / 2 |
| Semantic Redundancies in Image-Classification Datasets: The 10% You Don't Need | paper | full_text | 4 / 4 |
| Semantic Redundancies in Image-Classification Datasets: The 10% You Don't Need | paper | full_text | 3 / 3 |
| Deep Learning Techniques for Image Classification / Computer Vision / Computer Vision and Multi | web | web_snippet | 0 / 0 |
| Deep learning models for digital image processing: a review / Artificial Intelligence Review /  | web | web_snippet | 1 / 1 |
| NeurIPS Poster Surge Phenomenon in Optimal Learning Rate and Batch Size Scaling | web | web_snippet | 1 / 1 |
| Surge Phenomenon in Optimal Learning Rate and Batch Size Scaling | web | web_snippet | 1 / 1 |
| The heart of the internet | web | web_snippet | 4 / 4 |
| [1907.02549] Measuring the Data Efficiency of Deep Learning Methods | web | web_snippet | 0 / 0 |

**5. How do ViT and CNN compare in terms of image classification accuracy and data efficiency?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Comparing Vision Transformers and Convolutional Neural Networks for Image Classification: A Lit | paper | full_text | 4 / 5 |
| Comparing Vision Transformers and Convolutional Neural Networks for Image Classification: A Lit | paper | full_text | 4 / 5 |
| Comparison of Vision Transformers and Convolutional Neural Networks in Medical Image Analysis:  | paper | full_text | 4 / 4 |
| Convolutional neural network and vision transformer for image classification | paper | full_text | 5 / 5 |
| Convolutional neural network and vision transformer for image classification | paper | full_text | 3 / 3 |
| Depth-Wise Convolutions in Vision Transformers for efficient training on small datasets | paper | full_text | 2 / 4 |
| Depth-Wise Convolutions in Vision Transformers for efficient training on small datasets | paper | full_text | 3 / 3 |
| Is it Time to Replace CNNs with Transformers for Medical Images? | paper | full_text | 5 / 5 |
| Is it Time to Replace CNNs with Transformers for Medical Images? | paper | full_text | 4 / 5 |
| Next-ViT: Next Generation Vision Transformer for Efficient Deployment in Realistic Industrial S | paper | full_text | 3 / 5 |
| Next-ViT: Next Generation Vision Transformer for Efficient Deployment in Realistic Industrial S | paper | full_text | 2 / 3 |
| A Comparative Study of Convolutional Neural Networks and Vision Transformers for Agricultural I | web | web_snippet | 4 / 4 |
| Comparison of Vision Transformers and Convolutional Neural Networks in Medical Image Analysis:  | web | web_snippet | 1 / 1 |
| Performance comparison of Vision transformers and CNN ... | web | web_snippet | 1 / 1 |

## 4. Stage 3: aspects and coverage

An aspect is covered when at least 2 judge "yes" verdicts come from at least 2 sources. States: covered, uncovered (judged, too few yes), no candidates, unjudged (a verdict failed).

### 1. What are vision transformers (ViT)?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 18 = yes 9, partial 7, no 2, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How do vision transformers (ViT) differ from convolutional neural networks (CNN)? | covered | 2 | 2 |
| 2 | What are the main advantages of ViT? | covered | 4 | 3 |
| 3 | What are the main disadvantages of ViT? | covered | 3 | 2 |

### 2. What are CNNs?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 29 = yes 17, partial 6, no 6, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How do CNNs process image data? | covered | 5 | 5 |
| 2 | advantages of CNNs | covered | 6 | 5 |
| 3 | disadvantages of CNNs | covered | 6 | 3 |

Loop 2 (r1 triage, steps reselect, pool, queries): searched 1 aspect(s), covered 1 (0 by synthesis of several sources), sufficient True (strict rule: True), gap rule core, 51.6 s.

| Aspect | Status | Steps tried | Covered by | How | Before (yes/partial/no) | After (yes/partial, sources) |
|---|---|---|---|---|---|---|
| disadvantages of CNNs | covered | reselect | reselect | single claims | 0/2/2 | - |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|
| reselect | 1 | 3 | 12 | 1 | 47.5 | digest_failed=0, sources_tried=5 |

### 3. How is image classification accuracy measured and compared for different models?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 24 = yes 7, partial 6, no 11, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | common benchmarks for image classification | covered | 2 | 2 |
| 2 | common datasets for image classification | covered | 3 | 3 |
| 3 | metrics for evaluating image classification performance | covered | 2 | 2 |
| 4 | criteria for evaluating image classification performance | uncovered | 0 | 0 |

Uncovered details: What are the metrics and criteria for evaluating image classification performance?

Loop 2 (r1 triage, steps reselect, pool, queries): searched 0 aspect(s), covered 0 (0 by synthesis of several sources), sufficient True (strict rule: False), gap rule core, 0.0 s.

| Aspect | Status | Steps tried | Covered by | How | Before (yes/partial/no) | After (yes/partial, sources) |
|---|---|---|---|---|---|---|
| criteria for evaluating image classification performance | known_gap_no_evidence | - | - | - | 0/1/5 | 0/1, 1 |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|

### 4. How is data efficiency measured and compared for different models?

Sufficient: **True**; judge used: True; sources 10 (6 full text); judge candidates 22 = yes 6, partial 9, no 7, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What are the factors that affect data efficiency for image models? | covered | 6 | 5 |
| 2 | methods for measuring data efficiency for image models | covered | 3 | 3 |
| 3 | tools for measuring data efficiency for image models | covered | 2 | 2 |

Loop 2 (r1 triage, steps reselect, pool, queries): searched 1 aspect(s), covered 1 (1 by synthesis of several sources), sufficient True (strict rule: True), gap rule core, 304.0 s.

| Aspect | Status | Steps tried | Covered by | How | Before (yes/partial/no) | After (yes/partial, sources) |
|---|---|---|---|---|---|---|
| What are the factors that affect data efficiency for image models? | covered | reselect, pool, queries | queries | synthesis | 0/3/3 | - |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|
| reselect | 1 | 3 | 7 | 0 | 33.8 | digest_failed=0, sources_tried=3 |
| pool | 1 | 0 | 0 | 0 | 0.3 | note=pool empty, sources_tried=0 |
| queries | 1 | 6 | 17 | 1 | 265.6 | queries=4, new_web_kept=3, digest_failed=0, new_web_found=19, new_papers_kept=3, new_papers_found=4, new_papers_parsed=3 |

### 5. How do ViT and CNN compare in terms of image classification accuracy and data efficiency?

Sufficient: **True**; judge used: True; sources 9 (6 full text); judge candidates 39 = yes 4, partial 27, no 8, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What results have previous studies reported when comparing ViT and CNN on various benchmarks and datasets regarding image classification accuracy and data efficiency? | covered | 6 | 6 |
| 2 | What are the explanations for the differences between ViT and CNN in terms of image classification accuracy and data efficiency? | covered | 5 | 4 |
| 3 | What are the explanations for the similarities between ViT and CNN in terms of image classification accuracy and data efficiency? | uncovered | 0 | 0 |
| 4 | implications of choosing between ViT and CNN for different applications or scenarios | covered | 6 | 5 |
| 5 | recommendations for choosing between ViT and CNN for different applications or scenarios | covered | 2 | 2 |

Uncovered details: What are the explanations or interpretations for the differences or similarities between ViT and CNN in terms of accuracy and data efficiency?

Loop 2 (r1 triage, steps reselect, pool, queries): searched 2 aspect(s), covered 4 (3 by synthesis of several sources), sufficient True (strict rule: False), gap rule core, 154.8 s.

| Aspect | Status | Steps tried | Covered by | How | Before (yes/partial/no) | After (yes/partial, sources) |
|---|---|---|---|---|---|---|
| implications of choosing between ViT and CNN for different applications or scena | covered | - | synthesis | synthesis | 1/4/1 | - |
| recommendations for choosing between ViT and CNN for different applications or s | covered | reselect, pool | pool | single claims | 0/3/2 | - |
| What are the explanations for the differences between ViT and CNN in terms of im | covered | reselect | reselect | synthesis | 1/2/3 | - |
| What are the explanations for the similarities between ViT and CNN in terms of i | known_gap_no_evidence | - | - | - | 0/1/2 | 0/0, 0 |
| What results have previous studies reported when comparing ViT and CNN on variou | covered | - | synthesis | synthesis | 0/6/0 | - |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|
| reselect | 2 | 5 | 16 | 1 | 64.5 | digest_failed=0, sources_tried=5 |
| pool | 1 | 1 | 4 | 1 | 83.0 | parsed=1, digest_failed=0, sources_tried=3 |

## 5. Retrieval details

- Web search variants: [11, 10, 10, 10, 6] unique sources after de-duplication per sub-question (Tavily, 3 queries each, 5 results per query).
- Pre-filter lines: 110 candidates -> 109 cleared min_similarity (0.56) -> top 20 shortlisted; 93 candidates -> 93 cleared min_similarity (0.56) -> top 20 shortlisted; 95 candidates -> 95 cleared min_similarity (0.56) -> top 20 shortlisted; 85 candidates -> 82 cleared min_similarity (0.56) -> top 20 shortlisted; 63 candidates -> 63 cleared min_similarity (0.56) -> top 20 shortlisted
- Kept papers by source: {'openalex': 34, 'scopus': 19, 'both': 4, 'arxiv': 1}; requests to api.openalex.org in the log: 36
- Scopus: used
- Semantic Scholar: search skipped, probe failed - Semantic Scholar probe failed (HTTP 429): skipping Semantic Scholar search for this run; citation-enrichment batch calls answered 429: 0
- Citation enrichment: Citation enrichment: 1 arXiv-only papers to enrich; took 11s in total

## 6. Parsing details

- Attempted 24 papers, usable full text 23, 55 papers saved in the database.
- PDF obtained via: its own link: 17, the OpenAlex content API: 3, Unpaywall: 3; parse cache hits: 1; Unpaywall OA links found: 3; landing-page citation_pdf_url: 0
- Individual download failures: 12 -> HTTPStatusError: 6, ValueError: 6
- Headless-browser fallback: 0 tried, 0 failed; Docling fetch-by-URL attempts: 0; HTML full-text attempts that failed: 0

## 7. Groq and judge

- Stage 3: 38 digests for 5 sub-questions, 7 worker(s), 7 Groq key(s)
- Rate-limit parking events: 275; per key (events / parked seconds): ...3mla: 45 / 704s, ...Ef4D: 38 / 608s, ...KJJp: 37 / 625s, ...KaRe: 40 / 590s, ...X2Oj: 37 / 665s, ...uNUk: 36 / 646s, ...x1nP: 42 / 578s
- Judge batch latencies (s): [17.1, 23.4, 4.0, 13.2, 17.4, 4.2, 8.3, 22.7, 25.9, 7.0, 20.1, 6.6, 6.1, 5.1, 7.6, 3.9]

- Judge verdicts that came back as error: 0

## 7b. Stage 4: fact check

Claims after grouping: 121; labels {'unverified': 95, 'partially_supported': 24, 'supported': 1, 'contradicted': 1}; contradictions stored: 1; time 6m 00s.

| # | Sub-question | Digests | Claims | Clusters | Supported | Partly supported | Unverified | Contradicted |
|---|---|---|---|---|---|---|---|---|
| 1 | What are vision transformers (ViT)? | 8 | 30 | 21 | 0 | 5 | 16 | 0 |
| 2 | What are CNNs? | 11 | 31 | 25 | 0 | 7 | 18 | 0 |
| 3 | How is image classification accuracy measured and  | 8 | 28 | 20 | 0 | 5 | 15 | 0 |
| 4 | How is data efficiency measured and compared for d | 15 | 38 | 26 | 0 | 4 | 22 | 0 |
| 5 | How do ViT and CNN compare in terms of image class | 14 | 45 | 29 | 1 | 3 | 24 | 1 |

NLI pair cap: 158 quote/claim pairs passed the topic gate; only the 80 most similar go to NLI; 238 quote/claim pairs passed the topic gate; only the 80 most similar go to NLI; 407 quote/claim pairs passed the topic gate; only the 80 most similar go to NLI
- Conflict: Both statements address image classification performance of CNNs vs ViTs; one says performance is comparable, the other says ViTs perform better, which are opposite claims about the same metric.

## 8. Warnings and errors in the log (grouped)

| Level | Count | Message (numbers, urls and titles replaced) |
|---|---|---|
| ERROR | 2 | All PDF URLs failed for <id>: ValueError: ValueError('Non-PDF response (content-type: text/html) for <url> |
| WARNING | 10 | Failed to download from <url> ValueError: ValueError('Non-PDF response (content-type: text/html) for <url> |
| WARNING | 5 | Failed to download from <url> HTTPStatusError: HTTPStatusError('<text>') |
| WARNING | 5 | find_cached_parse: database connection error (attempt N/N): RemoteProtocolError: Server disconnected |
| WARNING | 3 | Stage N: N quote/claim pairs passed the topic gate; only the N most similar go to NLI |
| WARNING | 2 | SN gave up on '<text>' after N attempts (last status N) |
| WARNING | 2 | Semantic Scholar probe failed (HTTP N): skipping Semantic Scholar search for this run |
| WARNING | 2 | Failed to download from <url> HTTPStatusError: HTTPStatusError("Client error '<text>' for url '<url> more info |
| WARNING | 2 | Playwright fallback failed: ValueError: ValueError('<text>') |
| WARNING | 2 | database read failed (attempt N/N): RemoteProtocolError: Server disconnected |
| WARNING | 1 | get_papers_by_ids: database connection error (attempt N/N): RemoteProtocolError: Server disconnected |
| WARNING | 1 | PDFFigures parsing failed: Server error '<text>' for url '<url> |
| WARNING | 1 | Docling unavailable, using basic metadata: Server error '<text>' for url '<url> |

## 9. Checks (rule based, from the log)

- Semantic Scholar search was skipped (probe returned 429).
- Groq rate limiting: 275 parking events; digest generation took 6s.
- Longest phase: Stage 3 judge + coverage (per sub-question) (6m 37s, 31% of the run).

Warnings in the log: 36; errors: 2.

<!-- MANUAL NOTES (kept when this report is regenerated) -->

## 10. Notes

(write your reading of this run here)
