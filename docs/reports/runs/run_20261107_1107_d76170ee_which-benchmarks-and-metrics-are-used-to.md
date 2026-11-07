# Pipeline run report - Which benchmarks and metrics are used to evaluate the reasoning ability of large language models?

Generated 2026-11-07 13:57 by `scripts/pipeline_run_report.py` from `logs/pipeline.log` (run 15 in the file) and the database. Query id `d76170ee-fc49-4d07-9c4f-a1446bf6ff0c`.

## 1. Summary

| | |
|---|---|
| Question | Which benchmarks and metrics are used to evaluate the reasoning ability of large language models? |
| Domain anchor | (cached): 'AI evaluation' | context: Artificial intelligence evaluation: benchmarks and metrics are AI test suites measuring logical inference of large language models, not financial standards or psychological reasoning assessments. |
| Started / finished | 2026-11-07 11:07:48 / 11:27:29 |
| **Total execution time** | **19m 40s** (1180 s) |
| Sub-questions / search queries | 4 / 13 (per sub-question [3, 3, 3, 3]) |
| Plan source | plan-cache (stored plan reused, PLAN_CACHE=true) |
| Paper candidates retrieved (all sources), after the similarity floor, shortlisted | 463 candidates -> 460 cleared the similarity floor -> 80 shortlisted |
| **Papers kept after the relevance judge** | **61** (log: 61); 19 shortlisted papers rejected |
| **Web sources** | **54** (per sub-question [14, 14, 13, 13]) |
| Papers attempted for parsing | 22 (top-N per sub-question) |
| **Papers parsed to usable full text** | **20** of 22 attempted (18 from the parse cache) |
| Papers not parsed (all routes failed) | 0 download/route failures + 2 database/parse error(s); the rest of the shortfall is abstract-only |
| PDF download attempts that failed | 0 (individual URL failures; most papers recovered through another route) |
| Stage 3 digests | 32 (20 from full text, 0 from abstracts, 12 from web snippets) |
| Findings (verified / total) | 120 / 130 |
| Coverage sufficient | 0 of 4 sub-questions |
| Judge | 1m 54s in 6 batches; model id `judge-v2` (from .env at report time) |
| Groq rate limiting | 105 parking events, 1802 key-seconds parked |

## 2. Time per phase

| Phase | Start | End | Duration | Share |
|---|---|---|---|---|
| Planner (decompose, 4 sub-questions) | 11:07:48 | 11:07:50 | 2s | 0% |
| Web search (Tavily) | 11:07:50 | 11:08:07 | 16s | 1% |
| Paper search (arXiv, IEEE, OpenAlex, Semantic Scholar, Scopus) | 11:08:07 | 11:09:20 | 1m 13s | 6% |
| Embedding pre-filter + relevance judge | 11:09:20 | 11:12:31 | 3m 10s | 16% |
| Store papers in the database | 11:12:31 | 11:12:32 | 1s | 0% |
| PDF download + Docling parsing | 11:12:32 | 11:14:17 | 1m 44s | 9% |
| Stage 3 preparation (aspect split, chunking, embedding) | 11:14:17 | 11:23:38 | 9m 22s | 48% |
| Stage 3 digest generation (Groq) | 11:23:38 | 11:25:25 | 1m 46s | 9% |
| Stage 3 judge + coverage (per sub-question) | 11:25:25 | 11:27:29 | 2m 04s | 11% |
| **Total** | 11:07:48 | 11:27:29 | **19m 40s** | 100% |

## 3. Sub-questions: retrieval, filtering, parsing, Stage 3

| # | Sub-question | Pre-filter (cand. -> cleared -> shortlist) | Judge passed | Parsed full text | Web | Digests (full / abs / web) | Verified / total findings | Coverage |
|---|---|---|---|---|---|---|---|---|
| 1 | What is a large language model (LLM)? | 119 -> 117 -> 20 | 8 of 20 | 5 | 14 | 8 (5 / 0 / 3) | 25 / 27 | NOT sufficient |
| 2 | What is reasoning ability in the context of LLMs? | 118 -> 118 -> 20 | 16 of 20 | 6 | 14 | 8 (5 / 0 / 3) | 31 / 33 | NOT sufficient |
| 3 | What are benchmarks and metrics for evaluating the reasoning ability of LLMs? | 108 -> 108 -> 20 | 20 of 20 | 5 | 13 | 8 (5 / 0 / 3) | 34 / 38 | NOT sufficient |
| 4 | How can the benchmarks and metrics be used to improve the reasoning ability of LLMs? | 118 -> 117 -> 20 | 17 of 20 | 5 | 13 | 8 (5 / 0 / 3) | 30 / 32 | NOT sufficient |

- Relevance judge rejected 12 papers for [What is a large language model (LLM)?]. Examples: 'Evaluating Large Language Models: A Comprehensive Survey' (The paper focuses on evaluation methodologies and benchmarks rather than defining what a large language model is.); 'A Survey on Evaluation of Large Language Models' (The paper focuses on evaluation methods and benchmarks for LLMs rather than defining what an LLM is.); 'Inadequacies of Large Language Model Benchmarks in the Era o' (The paper evaluates existing benchmarks rather than defining what a large language model is.)
- Relevance judge rejected 4 papers for [What is reasoning ability in the context]. Examples: 'LatEval: An Interactive LLMs Evaluation Benchmark with Incom' (The paper focuses on lateral thinking and puzzle-solving rather than the general definition or measurement of logical reasoning ability in L); 'Verification of Reasoning Ability using BDI Logic and Large ' (The paper focuses on improving LLM performance in a specific game using BDI logic rather than defining or evaluating the general concept of ); 'Evaluating Mathematical Reasoning Across Large Language Mode' (The paper focuses specifically on mathematical reasoning capabilities rather than defining the general concept of reasoning ability in LLMs.)
- Relevance judge rejected 3 papers for [How can the benchmarks and metrics be us]. Examples: 'Inference-Time Computations for LLM Reasoning and Planning: ' (The paper evaluates existing inference-time techniques using a new benchmark but does not investigate how benchmarks themselves can be desig); 'AVENIBENCH: Accessible and Versatile Evaluation of Finance I' (The paper focuses exclusively on finance-specific benchmarks and does not address general methods for improving LLM reasoning abilities usin); 'Trojsten Benchmark: Evaluating LLM Problem-Solving in Slovak' (The paper focuses on creating a new benchmark for low-resource languages rather than investigating how benchmarks can improve LLM reasoning )

### Sources behind each sub-question's digests

**1. What is a large language model (LLM)?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Comprehensive Overview of Large Language Models | paper | full_text | 3 / 3 |
| A Survey on Large Language Models: Applications, Challenges, Limitations, and Practical Usage | paper | full_text | 5 / 5 |
| Large Language Models: A Survey | paper | full_text | 3 / 3 |
| Large language model applications for evaluation: Opportunities and ethical implications | paper | full_text | 3 / 5 |
| The Power of Words: An Overview of Large Language Models (LLMs) and Their Significance in AI | paper | full_text | 5 / 5 |
| AI Demystified: Introduction to large language models / University IT | web | web_snippet | 4 / 4 |
| Industrial applications of large language models / Scientific Reports | web | web_snippet | 0 / 0 |
| LLM Evaluation / IBM | web | web_snippet | 2 / 2 |

**2. What is reasoning ability in the context of LLMs?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Survey of Frontiers in LLM Reasoning: Inference Scaling, Learning to Reason, and Agentic Syst | paper | full_text | 4 / 5 |
| Are Large Language Models Really Good Logical Reasoners? A Comprehensive Evaluation and Beyond | paper | full_text | 5 / 5 |
| Logical Reasoning in Large Language Models: A Survey | paper | full_text | 5 / 5 |
| Measuring Reasoning Quality in LLMs: A Multi-Dimensional Behavioral Framework | paper | full_text | 4 / 5 |
| Thinking Machines: A Survey of LLM based Reasoning Strategies | paper | full_text | 3 / 3 |
| A Survey of Useful LLM Evaluation | web | web_snippet | 3 / 3 |
| Beyond Accuracy: Evaluating the Reasoning Behavior of Large Language Models - A Survey | web | web_snippet | 5 / 5 |
| WakenLLM: Evaluating Reasoning Potential and Stability in LLMs via Fine-Grained Benchmarking | web | web_snippet | 2 / 2 |

**3. What are benchmarks and metrics for evaluating the reasoning ability of LLMs?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Are Large Language Models Really Good Logical Reasoners? A Comprehensive Evaluation and Beyond | paper | full_text | 5 / 5 |
| Automating expert-level medical reasoning evaluation of large language models | paper | full_text | 5 / 5 |
| MME-Reasoning: A Comprehensive Benchmark for Logical Reasoning in MLLMs | paper | full_text | 2 / 5 |
| Measuring Reasoning Quality in LLMs: A Multi-Dimensional Behavioral Framework | paper | full_text | 5 / 5 |
| The Ouroboros of Benchmarking: Reasoning Evaluation in an Era of Saturation | paper | full_text | 4 / 5 |
| AI Benchmarks and Datasets for LLM Evaluation | web | web_snippet | 5 / 5 |
| Evaluating LLM Metrics Through Real-World Capabilities | web | web_snippet | 5 / 5 |
| Line Goes Up? Inherent Limitations of Benchmarks for Evaluating Large Language Models | web | web_snippet | 3 / 3 |

**4. How can the benchmarks and metrics be used to improve the reasoning ability of LLMs?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Automating expert-level medical reasoning evaluation of large language models | paper | full_text | 4 / 5 |
| Don't Make Your LLM an Evaluation Benchmark Cheater | paper | full_text | 5 / 5 |
| InfiMM-Eval: Complex Open-Ended Reasoning Evaluation For Multi-Modal Large Language Models | paper | full_text | 5 / 5 |
| Measuring Reasoning Quality in LLMs: A Multi-Dimensional Behavioral Framework | paper | full_text | 4 / 5 |
| The Ouroboros of Benchmarking: Reasoning Evaluation in an Era of Saturation | paper | full_text | 5 / 5 |
| Evaluating LLM Metrics Through Real-World Capabilities | web | web_snippet | 4 / 4 |
| LLM Evaluation: Metrics, Benchmarks & Best Practices / Codecademy | web | web_snippet | 3 / 3 |
| Mathematical Reasoning in Large Language Models: Benchmarks, Architectures, Evaluation, and Ope | web | web_snippet | 0 / 0 |

## 4. Stage 3: aspects and coverage

An aspect is covered when at least 2 judge "yes" verdicts come from at least 2 sources. States: covered, uncovered (judged, too few yes), no candidates, unjudged (a verdict failed).

### 1. What is a large language model (LLM)?

Sufficient: **False**; judge used: True; sources 7 (5 full text); judge candidates 21 = yes 11, partial 1, no 9, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How are LLMs trained? | covered | 3 | 3 |
| 2 | How are LLMs structured? | covered | 5 | 4 |
| 3 | What are the main applications of LLMs? | covered | 2 | 2 |
| 4 | What are the main challenges of LLMs? | uncovered | 1 | 1 |

Uncovered details: What are the main applications and challenges of LLMs?

### 2. What is reasoning ability in the context of LLMs?

Sufficient: **False**; judge used: True; sources 8 (5 full text); judge candidates 29 = yes 13, partial 6, no 10, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | how reasoning ability is defined | covered | 4 | 4 |
| 2 | how reasoning ability is measured | covered | 4 | 4 |
| 3 | What are the types of reasoning ability that LLMs can exhibit? | covered | 2 | 2 |
| 4 | What are the levels of reasoning ability that LLMs can exhibit? | uncovered | 1 | 1 |
| 5 | What are the factors that influence reasoning ability in LLMs? | covered | 2 | 2 |

Uncovered details: What are the types and levels of reasoning ability that LLMs can exhibit?

### 3. What are benchmarks and metrics for evaluating the reasoning ability of LLMs?

Sufficient: **False**; judge used: True; sources 8 (5 full text); judge candidates 39 = yes 18, partial 12, no 9, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | criteria of a good benchmark or metric | uncovered | 2 | 1 |
| 2 | characteristics of a good benchmark or metric | uncovered | 1 | 1 |
| 3 | What are the existing benchmarks for evaluating the reasoning ability of LLMs? | uncovered | 0 | 0 |
| 4 | What are the existing metrics for evaluating the reasoning ability of LLMs? | uncovered | 0 | 0 |
| 5 | How are the benchmarks and metrics categorized? | covered | 3 | 2 |
| 6 | How are the benchmarks and metrics compared? | covered | 2 | 2 |
| 7 | limitations of the current benchmarks and metrics | covered | 6 | 5 |
| 8 | gaps of the current benchmarks and metrics | covered | 4 | 4 |

Uncovered details: What are the criteria and characteristics of a good benchmark or metric?; What are the existing benchmarks and metrics for LLMs?

### 4. How can the benchmarks and metrics be used to improve the reasoning ability of LLMs?

Sufficient: **False**; judge used: True; sources 7 (5 full text); judge candidates 35 = yes 10, partial 16, no 9, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | best practices for using the benchmarks and metrics to improve the reasoning ability of LLMs | uncovered | 0 | 0 |
| 2 | methods for using the benchmarks and metrics to improve the reasoning ability of LLMs | uncovered | 0 | 0 |
| 3 | results from using the benchmarks and metrics to improve the reasoning ability of LLMs | covered | 2 | 2 |
| 4 | insights from using the benchmarks and metrics to improve the reasoning ability of LLMs | covered | 3 | 2 |
| 5 | What are the open problems for using the benchmarks and metrics? | uncovered | 1 | 1 |
| 6 | What are the future directions for using the benchmarks and metrics? | covered | 4 | 4 |

Uncovered details: What are the best practices and methods for using the benchmarks and metrics?; What are the open problems and future directions for using the benchmarks and metrics?

## 5. Retrieval details

- Web search variants: [14, 14, 13, 13] unique sources after de-duplication per sub-question (Tavily, 3 queries each, 5 results per query).
- Pre-filter lines: 119 candidates -> 117 cleared min_similarity (0.56) -> top 20 shortlisted; 118 candidates -> 118 cleared min_similarity (0.56) -> top 20 shortlisted; 108 candidates -> 108 cleared min_similarity (0.56) -> top 20 shortlisted; 118 candidates -> 117 cleared min_similarity (0.56) -> top 20 shortlisted
- Kept papers by source: {'openalex': 35, 'scopus': 25, 'both': 1}; requests to api.openalex.org in the log: 25
- Scopus: used
- Semantic Scholar: search skipped, probe failed - Semantic Scholar probe failed (HTTP 429): skipping Semantic Scholar search for this run; citation-enrichment batch calls answered 429: 0

## 6. Parsing details

- Attempted 22 papers, usable full text 20, 61 papers saved in the database.
- PDF obtained via: its own link: 2; parse cache hits: 18; Unpaywall OA links found: 0; landing-page citation_pdf_url: 0
- Individual download failures: 0 -> 
- Headless-browser fallback: 0 tried, 0 failed; Docling fetch-by-URL attempts: 0; HTML full-text attempts that failed: 0

Papers with NO usable text from any route:

| Paper | Reason |
|---|---|
| A Survey of Frontiers in LLM Reasoning: Inference Scaling, Learning to Reason, and Agentic | parse/database error: EOF occurred in violation of protocol (_ssl.c:2427) |
| Inadequacies of Large Language Model Benchmarks in the Era of Generative Artificial Intell | parse/database error: EOF occurred in violation of protocol (_ssl.c:2427) |

## 7. Groq and judge

- Stage 3: 32 digests for 4 sub-questions, 7 worker(s), 7 Groq key(s)
- Rate-limit parking events: 105; per key (events / parked seconds): ...3mla: 23 / 337s, ...Ef4D: 13 / 218s, ...KJJp: 8 / 202s, ...KaRe: 10 / 136s, ...X2Oj: 12 / 207s, ...uNUk: 15 / 337s, ...x1nP: 24 / 365s
- Judge batch latencies (s): [18.0, 23.6, 27.6, 8.6, 29.6, 6.6]

- Judge verdicts that came back as error: 0

## 8. Warnings and errors in the log (grouped)

| Level | Count | Message (numbers, urls and titles replaced) |
|---|---|---|
| ERROR | 2 | Failed to parse paper <id>: EOF occurred in violation of protocol (_ssl.c:N) |
| WARNING | 1 | SN gave up on '<text>' after N attempts (last status N) |
| WARNING | 1 | Semantic Scholar probe failed (HTTP N): skipping Semantic Scholar search for this run |
| WARNING | 1 | OpenAlex N on key ...CHgt for '<text>' (backoff N/N), pausing that key N.Ns |
| WARNING | 1 | database read failed (attempt N/N): WriteError: EOF occurred in violation of protocol (_ssl.c:N) |
| WARNING | 1 | Parse cache lookup failed for <id>: WriteError: EOF occurred in violation of protocol (_ssl.c:N) |

## 9. Checks (rule based, from the log)

- Semantic Scholar search was skipped (probe returned 429).
- 2 paper(s) failed at the parse/database step: A Survey of Frontiers in LLM Reasoning: Inference  (EOF occurred in violation of protocol (_ssl.c:2427)); Inadequacies of Large Language Model Benchmarks in (EOF occurred in violation of protocol (_ssl.c:2427))
- Groq rate limiting: 105 parking events; digest generation took 1m 46s.
- Longest phase: Stage 3 preparation (aspect split, chunking, embedding) (9m 22s, 48% of the run).

Warnings in the log: 5; errors: 2.

<!-- MANUAL NOTES (kept when this report is regenerated) -->

## 10. Notes (written by hand after reading the log and the database)

**Bottom line.** A complete run (19m 40s, no judge error, no digest failure) with good retrieval and extraction (61 papers kept, 20 of 22 attempted with full text, **120 of 130 findings verified, 92%**, 4.1 findings per digest) and **0 of 4 sub-questions sufficient**. The question was chosen to test list-type aspects, and it did what I predicted when I proposed it ("the judge might be too strict about one concrete item"): the two aspects that ARE the user's question, "What are the existing benchmarks for evaluating the reasoning ability of LLMs?" and "What are the existing metrics ...?", have **0 "yes" in 12 judged pairs (8 partial, 4 no)**, while the generic aspects next to them ("limitations", "gaps", "categorized", "compared") are covered. Two on-topic papers were also lost to a database error, and Stage 3 preparation took 9m 22s, twice the previous worst.

### Numbers

| | |
|---|---|
| Plan | 4 sub-questions, 13 queries [3, 3, 3, 3], from the plan cache (probably stored by the earlier, stopped run 14), anchor 'AI evaluation' |
| Retrieval | 463 candidates, 61 kept, 54 web sources; judge passed 8, 16, 20 and 17 of 20 |
| Parsing | 20 of 22 usable, 18 from the parse cache (topics overlap with Q1 to Q3); 2 papers lost to a database error (below) |
| Stage 3 | 32 digests (20 full text, 12 web) in 1m 46s on 7 keys; 130 findings, 120 verified; **124 judge pairs** (21 + 29 + 39 + 35), 0 errors |
| Groq | 105 parking events, 1802 key-seconds (longest single park 42 s) |
| Coverage | aspects covered 14 of 23: sub-question 1: 3 of 4; 2: 4 of 5; 3: 4 of 8; 4: 3 of 6 |

### What went wrong, in order of impact

1. **The aspects that are the question get 0 "yes"; the generic ones get covered.** The core sub-question's four detail questions became 8 aspects. Covered: "how are they categorized" (3 yes), "compared" (2), "limitations" (6 yes from 5 sources), "gaps" (4). Not covered: "criteria of a good benchmark" (2 yes, 1 source), "characteristics" (1), **"existing benchmarks" (0 yes)** and **"existing metrics" (0 yes)**. So the sub-question reports, in effect, "here are the limitations of benchmarks" and not "here are the benchmarks". The judge's reasons for the list aspects are uniform: "the claim only describes one specific benchmark (GLoRE / ZebraLogic / MedThink-Bench) rather than listing the existing benchmarks"; "describes metrics proposed by the specific paper rather than listing the existing metrics in the broader field". A paper names the benchmarks it uses; no single claim lists "the" benchmarks, so every claim is partial, and two "yes" from two sources cannot happen. Together the claims DO answer the aspect (GLoRE, ZebraLogic, MedThink-Bench, a 60,000-problem causal benchmark; BLEU, ROUGE-L, METEOR, LLM-as-a-judge, precision/recall/F1). This is the same strictness as in Q3 (known limit 3.15), now on a second aspect type.
2. **A sub-question the user did not ask.** Sub-question 4, "How can the benchmarks and metrics be used to improve the reasoning ability of LLMs?", asks how to IMPROVE reasoning; the user asked which benchmarks and metrics are used to EVALUATE it. It spends 5 parsed papers and 8 digests, and its aspects are the generic families again (best practices, methods, results, insights, open problems, future directions). Sub-question 1 is the background question "What is a large language model?" for the third question in a row (5 parsed papers, 8 digests; its "main challenges" aspect has 1 yes). So 2 of the 4 sub-questions, half the budget, are not the question (known limits 1.3, 3.12).
3. **Two on-topic papers lost to a database error.** "Inadequacies of Large Language Model Benchmarks in the Era of Generative Artificial Intelligence" and "A Survey of Frontiers in LLM Reasoning" failed at the parse/store step with `EOF occurred in violation of protocol (_ssl.c:2427)`; the log has the same error for the parse-cache lookup and for one API read (that one was retried). The first of the two is about the shortcomings of benchmarks, the exact subject of the core sub-question. The pipeline's own database calls are not retried (planned item B8), and this is the second run in which they cost a relevant paper.
4. **Stage 3 preparation took 9m 22s (48% of the run).** The log shows two gaps of about 4 minutes (11:14:26 to 11:18:39 and 11:18:41 to 11:22:24) between the aspect splits of successive sub-questions, which is the chunking and embedding of that sub-question's papers. Earlier runs needed 1m 55s (3 sub-questions) to 5m 30s (5). The relevance pre-filter of the same run was also slow (3m 10s against about 2m), while the network phases (web search, paper search, digests) were normal. Both slow phases run the bge embedding model on the CPU, so a likely cause is other work using the machine at the same time (the web app was being developed on this computer); I did not verify it. The chunk-embedding cache (B5) would remove most of this cost.

### What this run shows about the judge on list-type aspects
12 verdicts (6 for benchmarks, 6 for metrics) were read in full: 0 "yes", 8 "partial", 4 "no". The 4 "no" are claims about benchmarks in general ("benchmark scores are unreliable", "ChatGPT and GPT-4 outperform open-source models on GLoRE"), which rightly do not list anything. The 8 "partial" are the problem: each names a specific benchmark or metric, correctly. I agree with the judge's literal reading of the aspect; the mismatch is between "list the existing X" as an aspect and a coverage rule that needs two single claims to be complete answers. Possible remedies are in the plan (B1): word list-type aspects as "which X are used" so that one named X is a complete answer, or accept complementary partial claims from distinct sources only if a labeled test shows it is safe. No change made here.

### What worked
- Retrieval found the right literature for the core sub-question (GLoRE, ZebraLogic, MedThink-Bench, causal-reasoning and logical-reasoning benchmark papers); the anchor 'AI evaluation' and its context kept financial and psychological "reasoning/metrics" papers out.
- The tolerant quote verifier: 92% verified; digests 4.1 findings each (the topic aspect is off).
- 7 Groq keys: digests 1m 46s for 32 sources.
- Judge: 124 pairs, 0 errors.

### Next checks
- [ ] Label the judged pairs of the two list aspects of this run and the Q3 core sub-question against one written rule (planned item B1).
- [ ] B8: retry the pipeline's database calls (second run with a relevant paper lost).
- [ ] Repeat Stage 3 preparation timing when the computer is otherwise idle, to confirm the CPU explanation.
- [ ] Run Q5 and Q6.

(To regenerate the tables above after another run: `python scripts/pipeline_run_report.py --run N`; these notes are kept.)
