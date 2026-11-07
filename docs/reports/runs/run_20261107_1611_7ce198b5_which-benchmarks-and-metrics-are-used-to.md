# Pipeline run report - Which benchmarks and metrics are used to evaluate the reasoning ability of large language models?

Generated 2026-11-07 16:35 by `scripts/pipeline_run_report.py` from `logs/pipeline.log` (run 21 in the file) and the database. Query id `7ce198b5-0fb6-432c-a071-8c9711226ff1`.

## 1. Summary

| | |
|---|---|
| Question | Which benchmarks and metrics are used to evaluate the reasoning ability of large language models? |
| Domain anchor | (cached): 'AI evaluation' | context: Artificial intelligence evaluation: benchmarks and metrics are AI test suites measuring logical inference of large language models, not financial standards or psychological reasoning assessments. |
| Started / finished | 2026-11-07 16:11:12 / 16:27:05 |
| **Total execution time** | **15m 53s** (953 s) |
| Sub-questions / search queries | 4 / 13 (per sub-question [3, 3, 3, 3]) |
| Plan source | plan-cache (stored plan reused, PLAN_CACHE=true) |
| Paper candidates retrieved (all sources), after the similarity floor, shortlisted | 463 candidates -> 460 cleared the similarity floor -> 80 shortlisted |
| **Papers kept after the relevance judge** | **71** (log: 62); 18 shortlisted papers rejected |
| **Web sources** | **60** (per sub-question [14, 13, 11, 13]) |
| Papers attempted for parsing | 20 (top-N per sub-question) |
| **Papers parsed to usable full text** | **20** of 20 attempted (20 from the parse cache) |
| Papers not parsed (all routes failed) | 0 download/route failures + 0 database/parse error(s); the rest of the shortfall is abstract-only |
| PDF download attempts that failed | 0 (individual URL failures; most papers recovered through another route) |
| Stage 3 digests | 57 (39 from full text, 0 from abstracts, 18 from web snippets) |
| Findings (verified / total) | 184 / 210 |
| Coverage sufficient | 1 of 4 sub-questions |
| Judge | 2m 41s in 12 batches; model id `judge-v2` (from .env at report time) |
| Groq rate limiting | 119 parking events, 8422 key-seconds parked |

## 2. Time per phase

| Phase | Start | End | Duration | Share |
|---|---|---|---|---|
| Planner (decompose, 4 sub-questions) | 16:11:12 | 16:11:14 | 1s | 0% |
| Web search (Tavily) | 16:11:14 | 16:11:25 | 11s | 1% |
| Paper search (arXiv, IEEE, OpenAlex, Semantic Scholar, Scopus) | 16:11:25 | 16:12:20 | 56s | 6% |
| Embedding pre-filter + relevance judge | 16:12:20 | 16:13:46 | 1m 26s | 9% |
| Store papers in the database | 16:13:46 | 16:13:47 | 1s | 0% |
| PDF download + Docling parsing | 16:13:47 | 16:14:01 | 14s | 1% |
| Stage 3 preparation (aspect split, chunking, embedding) | 16:14:01 | 16:14:19 | 18s | 2% |
| Stage 3 digest generation (Groq) | 16:14:19 | 16:16:11 | 1m 52s | 12% |
| Stage 3 judge + coverage (per sub-question) | 16:16:11 | 16:27:05 | 10m 54s | 69% |
| **Total** | 16:11:12 | 16:27:05 | **15m 53s** | 100% |

Loop 2 (second search for uncovered aspects) is part of the judge + coverage phase above: 9m 02s by its own step timings (57% of the run). Its searches, parses and filters are NOT counted in the retrieval figures of this report; it stored 9 new paper(s) and 9 new web page(s) with the run, so the stored counts of papers and web sources are higher than the log counts by these numbers.

## 3. Sub-questions: retrieval, filtering, parsing, Stage 3

| # | Sub-question | Pre-filter (cand. -> cleared -> shortlist) | Judge passed | Parsed full text | Web | Digests (full / abs / web) | Verified / total findings | Coverage |
|---|---|---|---|---|---|---|---|---|
| 1 | What is a large language model (LLM)? | 119 -> 117 -> 20 | 8 of 20 | 5 | 14 | 8 (5 / 0 / 3) | 23 / 26 | sufficient |
| 2 | What is reasoning ability in the context of LLMs? | 118 -> 118 -> 20 | 17 of 20 | 11 | 16 | 21 (15 / 0 / 6) | 58 / 65 | NOT sufficient |
| 3 | What are benchmarks and metrics for evaluating the reasoning ability of LLMs? | 108 -> 108 -> 20 | 20 of 20 | 10 | 14 | 20 (14 / 0 / 6) | 71 / 84 | NOT sufficient |
| 4 | How can the benchmarks and metrics be used to improve the reasoning ability of LLMs? | 118 -> 117 -> 20 | 17 of 20 | 10 | 16 | 8 (5 / 0 / 3) | 32 / 35 | NOT sufficient |

- Relevance judge rejected 12 papers for [What is a large language model (LLM)?]. Examples: 'Evaluating Large Language Models: A Comprehensive Survey' (The paper focuses on evaluation methodologies and benchmarks rather than defining what a large language model is.); 'A Survey on Evaluation of Large Language Models' (The paper focuses on evaluation methods and benchmarks for LLMs rather than defining what an LLM is.); 'Inadequacies of Large Language Model Benchmarks in the Era o' (The paper evaluates existing benchmarks rather than defining what a large language model is.)
- Relevance judge rejected 3 papers for [What is reasoning ability in the context]. Examples: 'LatEval: An Interactive LLMs Evaluation Benchmark with Incom' (The paper focuses on lateral thinking and puzzle-solving rather than the general definition or measurement of logical reasoning ability in L); 'Evaluating Mathematical Reasoning Across Large Language Mode' (The paper focuses specifically on mathematical reasoning capabilities rather than defining the general concept of reasoning ability in LLMs.); 'Evaluating the Intelligence of large language models: A comp' (The paper uses human IQ tests as a proxy for LLM intelligence rather than defining or analyzing the intrinsic reasoning ability of LLMs them)
- Relevance judge rejected 3 papers for [How can the benchmarks and metrics be us]. Examples: 'Inference-Time Computations for LLM Reasoning and Planning: ' (The paper focuses on improving reasoning through inference-time techniques rather than evaluating how benchmarks and metrics themselves can ); 'AVENIBENCH: Accessible and Versatile Evaluation of Finance I' (The paper focuses exclusively on finance-specific benchmarks and does not address general methods for improving LLM reasoning abilities usin); 'Trojsten Benchmark: Evaluating LLM Problem-Solving in Slovak' (The paper focuses on creating a new benchmark for low-resource languages rather than investigating how benchmarks can improve LLM reasoning )

### Sources behind each sub-question's digests

**1. What is a large language model (LLM)?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Comprehensive Overview of Large Language Models | paper | full_text | 4 / 5 |
| A Survey on Large Language Models: Applications, Challenges, Limitations, and Practical Usage | paper | full_text | 3 / 4 |
| Large Language Models: A Survey | paper | full_text | 5 / 5 |
| Large language model applications for evaluation: Opportunities and ethical implications | paper | full_text | 3 / 4 |
| The Power of Words: An Overview of Large Language Models (LLMs) and Their Significance in AI | paper | full_text | 5 / 5 |
| A Comprehensive Overview of Large Language Models | web | web_snippet | 2 / 2 |
| Industrial applications of large language models / Scientific Reports | web | web_snippet | 0 / 0 |
| LLM Evaluation / IBM | web | web_snippet | 1 / 1 |

**2. What is reasoning ability in the context of LLMs?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Survey of Frontiers in LLM Reasoning: Inference Scaling, Learning to Reason, and Agentic Syst | paper | full_text | 2 / 4 |
| A Survey of Frontiers in LLM Reasoning: Inference Scaling, Learning to Reason, and Agentic Syst | paper | full_text | 2 / 2 |
| A Survey of Useful LLM Evaluation | paper | full_text | 2 / 2 |
| Are Large Language Models Really Good Logical Reasoners? A Comprehensive Evaluation and Beyond | paper | full_text | 2 / 5 |
| Are Large Language Models Really Good Logical Reasoners? A Comprehensive Evaluation and Beyond | paper | full_text | 4 / 4 |
| InfiMM-Eval: Complex Open-Ended Reasoning Evaluation For Multi-Modal Large Language Models | paper | full_text | 3 / 3 |
| LogicVista: Multimodal LLM Logical Reasoning Benchmark in Visual Contexts | paper | full_text | 5 / 5 |
| Logical Reasoning in Large Language Models: A Survey | paper | full_text | 2 / 3 |
| Logical Reasoning in Large Language Models: A Survey | paper | full_text | 5 / 5 |
| MME-Reasoning: A Comprehensive Benchmark for Logical Reasoning in MLLMs | paper | full_text | 4 / 4 |
| Measuring Reasoning Quality in LLMs: A Multi-Dimensional Behavioral Framework | paper | full_text | 5 / 5 |
| Measuring Reasoning Quality in LLMs: A Multi-Dimensional Behavioral Framework | paper | full_text | 2 / 2 |
| Skill-Mix: a Flexible and Expandable Family of Evaluations for AI models | paper | full_text | 1 / 2 |
| The Ouroboros of Benchmarking: Reasoning Evaluation in an Era of Saturation | paper | full_text | 1 / 1 |
| Thinking Machines: A Survey of LLM based Reasoning Strategies | paper | full_text | 3 / 3 |
| A Survey of Useful LLM Evaluation | web | web_snippet | 2 / 2 |
| Beyond Accuracy: Evaluating the Reasoning Behavior of Large Language Models - A Survey | web | web_snippet | 5 / 5 |
| Evaluating Step-by-step Reasoning Traces: A Survey | web | web_snippet | 4 / 4 |
| From LLM Reasoning to Autonomous AI Agents: A Comprehensive ... | web | web_snippet | 1 / 1 |
| Quantifying the reasoning abilities of LLMs on clinical cases / Nature Communications | web | web_snippet | 2 / 2 |
| https://ewww.gist.ac.kr/en/html/sub06/060202.html?mode=D&no=216691&file_id=75451 | web | web_snippet | 1 / 1 |

**3. What are benchmarks and metrics for evaluating the reasoning ability of LLMs?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Are Large Language Models Really Good Logical Reasoners? A Comprehensive Evaluation and Beyond | paper | full_text | 4 / 5 |
| Are Large Language Models Really Good Logical Reasoners? A Comprehensive Evaluation and Beyond | paper | full_text | 3 / 5 |
| Automating expert-level medical reasoning evaluation of large language models | paper | full_text | 4 / 5 |
| Automating expert-level medical reasoning evaluation of large language models | paper | full_text | 5 / 5 |
| Benchmark Radar: A Living Database and Search Engine for AI Benchmarks and Evaluation | paper | full_text | 5 / 5 |
| Inadequacies of Large Language Model Benchmarks in the Era of Generative Artificial Intelligenc | paper | full_text | 1 / 5 |
| Inadequacies of Large Language Model Benchmarks in the Era of Generative Artificial Intelligenc | paper | full_text | 4 / 4 |
| InfiMM-Eval: Complex Open-Ended Reasoning Evaluation For Multi-Modal Large Language Models | paper | full_text | 4 / 5 |
| JudgeBench: A Benchmark for Evaluating LLM-based Judges | paper | full_text | 3 / 3 |
| MME-Reasoning: A Comprehensive Benchmark for Logical Reasoning in MLLMs | paper | full_text | 5 / 5 |
| MME-Reasoning: A Comprehensive Benchmark for Logical Reasoning in MLLMs | paper | full_text | 5 / 5 |
| Measuring Reasoning Quality in LLMs: A Multi-Dimensional Behavioral Framework | paper | full_text | 4 / 5 |
| Measuring Reasoning Quality in LLMs: A Multi-Dimensional Behavioral Framework | paper | full_text | 3 / 5 |
| The Ouroboros of Benchmarking: Reasoning Evaluation in an Era of Saturation | paper | full_text | 3 / 3 |
| AI Benchmarks and Datasets for LLM Evaluation | web | web_snippet | 3 / 4 |
| Evaluating LLM Metrics Through Real-World Capabilities | web | web_snippet | 5 / 5 |
| How to Evaluate the Reasoning Abilities of Large Language Models ? | web | web_snippet | 1 / 1 |
| Line Goes Up? Inherent Limitations of Benchmarks for Evaluating Large Language Models | web | web_snippet | 2 / 2 |
| Measuring Reasoning Quality in LLMs: A Multi-Dimensional Behavioral Framework | web | web_snippet | 3 / 3 |
| What Defines Good Reasoning in LLMs?Dissecting Reasoning Steps with Multi-Aspect Evaluation | web | web_snippet | 4 / 4 |

**4. How can the benchmarks and metrics be used to improve the reasoning ability of LLMs?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Automating expert-level medical reasoning evaluation of large language models | paper | full_text | 4 / 5 |
| Don't Make Your LLM an Evaluation Benchmark Cheater | paper | full_text | 5 / 5 |
| InfiMM-Eval: Complex Open-Ended Reasoning Evaluation For Multi-Modal Large Language Models | paper | full_text | 3 / 5 |
| Measuring Reasoning Quality in LLMs: A Multi-Dimensional Behavioral Framework | paper | full_text | 5 / 5 |
| The Ouroboros of Benchmarking: Reasoning Evaluation in an Era of Saturation | paper | full_text | 5 / 5 |
| Evaluating LLM Metrics Through Real-World Capabilities | web | web_snippet | 4 / 4 |
| LLM Evaluation: Metrics, Benchmarks & Best Practices / Codecademy | web | web_snippet | 5 / 5 |
| Mathematical Reasoning in Large Language Models: Benchmarks, Architectures, Evaluation, and Ope | web | web_snippet | 1 / 1 |

## 4. Stage 3: aspects and coverage

An aspect is covered when at least 2 judge "yes" verdicts come from at least 2 sources. States: covered, uncovered (judged, too few yes), no candidates, unjudged (a verdict failed).

### 1. What is a large language model (LLM)?

Sufficient: **True**; judge used: True; sources 7 (5 full text); judge candidates 22 = yes 10, partial 5, no 7, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How are LLMs trained? | covered | 4 | 3 |
| 2 | How are LLMs structured? | covered | 2 | 2 |
| 3 | main applications of LLMs | covered | 2 | 2 |
| 4 | challenges of LLMs | covered | 2 | 2 |

### 2. What is reasoning ability in the context of LLMs?

Sufficient: **False**; judge used: True; sources 17 (11 full text); judge candidates 30 = yes 17, partial 10, no 3, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | how reasoning ability is defined | covered | 4 | 3 |
| 2 | how reasoning ability is measured | covered | 6 | 5 |
| 3 | What are the types of reasoning ability that LLMs can exhibit? | covered | 4 | 4 |
| 4 | What are the levels of reasoning ability that LLMs can exhibit? | uncovered | 1 | 1 |
| 5 | What are the factors that influence reasoning ability in LLMs? | covered | 2 | 2 |

Uncovered details: What are the types and levels of reasoning ability that LLMs can exhibit?

Loop 2 (r1 triage, steps reselect, pool, queries): searched 1 aspect(s), covered 0, 178.7 s.

| Aspect | Status | Steps tried | Covered by | Before (yes/partial/no) |
|---|---|---|---|---|
| What are the levels of reasoning ability that LLMs can exhibit? | known_gap | reselect, pool, queries | - | 1/1/1 |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|
| reselect | 1 | 4 | 13 | 0 | 14.3 | sources_tried=5 |
| pool | 1 | 3 | 11 | 0 | 44.1 | parsed=3, sources_tried=3 |
| queries | 1 | 6 | 9 | 0 | 120.3 | queries=4, new_web_kept=3, new_web_found=20, new_papers_kept=3, new_papers_found=9, new_papers_parsed=3 |

### 3. What are benchmarks and metrics for evaluating the reasoning ability of LLMs?

Sufficient: **False**; judge used: True; sources 15 (9 full text); judge candidates 44 = yes 24, partial 12, no 8, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | criteria of a good benchmark or metric for evaluating the reasoning ability of LLMs | covered | 3 | 3 |
| 2 | characteristics of a good benchmark or metric for evaluating the reasoning ability of LLMs | covered | 2 | 2 |
| 3 | benchmarks for evaluating the reasoning ability of LLMs | covered | 3 | 3 |
| 4 | metrics for evaluating the reasoning ability of LLMs | covered | 4 | 4 |
| 5 | How are benchmarks and metrics categorized for evaluating the reasoning ability of LLMs? | covered | 3 | 3 |
| 6 | How are benchmarks and metrics compared for evaluating the reasoning ability of LLMs? | uncovered | 1 | 1 |
| 7 | What are the limitations of the current benchmarks and metrics? | covered | 4 | 4 |
| 8 | What are the gaps of the current benchmarks and metrics? | covered | 4 | 3 |

Uncovered details: How are the benchmarks and metrics categorized and compared?

Loop 2 (r1 triage, steps reselect, pool, queries): searched 3 aspect(s), covered 3, 262.2 s.

| Aspect | Status | Steps tried | Covered by | Before (yes/partial/no) |
|---|---|---|---|---|
| criteria of a good benchmark or metric for evaluating the reasoning ability of L | covered | reselect | reselect | 1/1/3 |
| How are benchmarks and metrics compared for evaluating the reasoning ability of  | known_gap_skipped_triage | - | - | 1/0/1 |
| How are benchmarks and metrics categorized for evaluating the reasoning ability  | covered | reselect, pool | pool | 1/1/1 |
| characteristics of a good benchmark or metric for evaluating the reasoning abili | covered | reselect, pool, queries | queries | 0/3/2 |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|
| reselect | 3 | 5 | 20 | 1 | 29.5 | sources_tried=5 |
| pool | 2 | 2 | 7 | 1 | 14.2 | parsed=2, sources_tried=3 |
| queries | 1 | 5 | 16 | 1 | 218.5 | queries=2, new_web_kept=3, new_web_found=9, new_papers_kept=3, new_papers_found=12, new_papers_parsed=3 |

### 4. How can the benchmarks and metrics be used to improve the reasoning ability of LLMs?

Sufficient: **False**; judge used: False; sources 8 (5 full text); judge candidates 35 = yes 9, partial 14, no 11, error 1; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What are the best practices for using benchmarks and metrics to improve the reasoning ability of LLMs? | unjudged | 0 | 0 |
| 2 | What methods can be used for applying benchmarks and metrics to improve the reasoning ability of LLMs? | covered | 2 | 2 |
| 3 | What are the results from using the benchmarks and metrics to improve the reasoning ability of LLMs? | covered | 2 | 2 |
| 4 | What are the insights from using the benchmarks and metrics to improve the reasoning ability of LLMs? | uncovered | 2 | 1 |
| 5 | What are the open problems for using the benchmarks and metrics? | uncovered | 0 | 0 |
| 6 | What are the future directions for using the benchmarks and metrics? | covered | 3 | 3 |

Uncovered details: What are the best practices and methods for using the benchmarks and metrics?; What are the results and insights from using the benchmarks and metrics?; What are the open problems and future directions for using the benchmarks and metrics?

Loop 2 (r1 triage, steps reselect, pool, queries): searched 2 aspect(s), covered 0, 101.4 s.

| Aspect | Status | Steps tried | Covered by | Before (yes/partial/no) |
|---|---|---|---|---|
| What are the open problems for using the benchmarks and metrics? | known_gap | reselect, pool, queries | - | 0/4/2 |
| What are the insights from using the benchmarks and metrics to improve the reaso | known_gap | reselect, pool, queries | - | 2/3/1 |
| What are the best practices for using benchmarks and metrics to improve the reas | unjudged_not_searched | - | - | -/-/- |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|
| reselect | 2 | 0 | 0 | 0 | 1.3 | sources_tried=5 |
| pool | 2 | 0 | 0 | 0 | 1.5 | parsed=2, sources_tried=3 |
| queries | 2 | 0 | 0 | 0 | 98.5 | queries=3, new_web_kept=3, new_web_found=15, new_papers_kept=3, new_papers_found=25, new_papers_parsed=3 |

## 5. Retrieval details

- Web search variants: [14, 13, 11, 13] unique sources after de-duplication per sub-question (Tavily, 3 queries each, 5 results per query).
- Pre-filter lines: 119 candidates -> 117 cleared min_similarity (0.56) -> top 20 shortlisted; 118 candidates -> 118 cleared min_similarity (0.56) -> top 20 shortlisted; 108 candidates -> 108 cleared min_similarity (0.56) -> top 20 shortlisted; 118 candidates -> 117 cleared min_similarity (0.56) -> top 20 shortlisted
- Kept papers by source: {'openalex': 43, 'scopus': 26, 'both': 1, 'arxiv': 1}; requests to api.openalex.org in the log: 42
- Scopus: used
- Semantic Scholar: search skipped, probe failed - Semantic Scholar probe failed (HTTP 429): skipping Semantic Scholar search for this run; citation-enrichment batch calls answered 429: 0

## 6. Parsing details

- Attempted 20 papers, usable full text 20, 62 papers saved in the database.
- PDF obtained via: -; parse cache hits: 20; Unpaywall OA links found: 0; landing-page citation_pdf_url: 0
- Individual download failures: 0 -> 
- Headless-browser fallback: 0 tried, 0 failed; Docling fetch-by-URL attempts: 0; HTML full-text attempts that failed: 0

## 7. Groq and judge

- Stage 3: 32 digests for 4 sub-questions, 7 worker(s), 7 Groq key(s)
- Rate-limit parking events: 119; per key (events / parked seconds): ...3mla: 3 / 1118s, ...Ef4D: 19 / 1789s, ...KJJp: 23 / 1051s, ...KaRe: 21 / 912s, ...X2Oj: 24 / 1404s, ...uNUk: 27 / 1086s, ...x1nP: 2 / 1062s
- Judge batch latencies (s): [17.7, 22.5, 8.3, 8.0, 6.1, 27.3, 7.8, 16.2, 5.8, 7.8, 27.9, 5.3]

- Judge verdicts that came back as error: 1 -> aspect 1 of 'Measuring Reasoning Quality in LLMs: A M': the judge returned no verdict and gave no error text | raw output: {"quote_supports_claim": "partial", "answers_aspect":

## 8. Warnings and errors in the log (grouped)

| Level | Count | Message (numbers, urls and titles replaced) |
|---|---|---|
| ERROR | 28 | Digest generation failed: all N Groq key(s) are rate limited for Ns |
| WARNING | 7 | SN gave up on '<text>' after N attempts (last status N) |
| WARNING | 5 | _upsert_parsed: database connection error (attempt N/N): RemoteProtocolError: Server disconnected |
| WARNING | 4 | Semantic Scholar probe failed (HTTP N): skipping Semantic Scholar search for this run |
| WARNING | 3 | find_cached_parse: database connection error (attempt N/N): RemoteProtocolError: Server disconnected |
| WARNING | 2 | get_retrieved_paper: database connection error (attempt N/N): WriteError: EOF occurred in violation of protoco |
| WARNING | 1 | _upsert_parsed: database connection error (attempt N/N): WriteError: EOF occurred in violation of protocol (_s |
| WARNING | 1 | get_papers_for_stageN: database connection error (attempt N/N): RemoteProtocolError: Server disconnected |
| WARNING | 1 | Semantic Scholar gave up N searches in a row: skipping it for the rest of this run |
| WARNING | 1 | Judge verdict failed: aspect N, source NdbN-N, claim '<text>': the judge returned no verdict and gave no error |
| WARNING | 1 | Judge: N of N item(s) in this batch failed |

## 9. Checks (rule based, from the log)

- Semantic Scholar search was skipped (probe returned 429).
- Sub-question 'How can the benchmarks and metrics be used to improve the reasoning ability of LLMs?': 1 unjudged aspect(s) (a judge verdict failed): ['What are the best practices for using benchmarks and metrics to improve the reasoning ability of LLMs?']
- Groq rate limiting: 119 parking events; digest generation took 1m 52s.
- Longest phase: Stage 3 judge + coverage (per sub-question) (10m 54s, 69% of the run).

Warnings in the log: 26; errors: 28.

<!-- MANUAL NOTES (kept when this report is regenerated) -->

## 10. Notes

(write your reading of this run here)
