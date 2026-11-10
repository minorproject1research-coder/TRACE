# Pipeline run report - How does retrieval-augmented generation compare with fine-tuning for adding domain knowledge to large language models?

Generated 2026-11-10 17:03 by `scripts/pipeline_run_report.py` from `logs/pipeline.log` (run 33 in the file) and the database. Query id `22903fa8-d9e4-40b1-9675-cb60cecc1db9`.

## 1. Summary

| | |
|---|---|
| Question | How does retrieval-augmented generation compare with fine-tuning for adding domain knowledge to large language models? |
| Domain anchor | '' | context: - |
| Started / finished | 2026-11-10 16:28:35 / 16:47:58 |
| **Total execution time** | **19m 23s** (1163 s) |
| Sub-questions / search queries | 5 / 12 (per sub-question [3, 2, 2, 3, 2]) |
| Plan source | planner |
| Paper candidates retrieved (all sources), after the similarity floor, shortlisted | 475 candidates -> 418 cleared the similarity floor -> 100 shortlisted |
| **Papers kept after the relevance judge** | **62** (log: 62); 38 shortlisted papers rejected |
| **Web sources** | **55** (per sub-question [14, 9, 10, 12, 10]) |
| Papers attempted for parsing | 31 (top-N per sub-question) |
| **Papers parsed to usable full text** | **20** of 31 attempted (2 from the parse cache) |
| Papers not parsed (all routes failed) | 10 download/route failures + 0 database/parse error(s); the rest of the shortfall is abstract-only |
| PDF download attempts that failed | 18 (individual URL failures; most papers recovered through another route) |
| Stage 3 digests | 40 (20 from full text, 5 from abstracts, 15 from web snippets) |
| Findings (verified / total) | 123 / 134 |
| Coverage sufficient | 5 of 5 sub-questions |
| Judge | 1m 44s in 6 batches; model id `judge-v2` (from .env at report time) |
| Groq rate limiting | 195 parking events, 3345 key-seconds parked |

## 2. Time per phase

| Phase | Start | End | Duration | Share |
|---|---|---|---|---|
| Planner (decompose, 5 sub-questions) | 16:28:35 | 16:29:10 | 34s | 3% |
| Web search (Tavily) | 16:29:10 | 16:29:25 | 15s | 1% |
| Paper search (arXiv, IEEE, OpenAlex, Semantic Scholar, Scopus) | 16:29:25 | 16:30:00 | 36s | 3% |
| Embedding pre-filter + relevance judge | 16:30:00 | 16:31:00 | 1m 00s | 5% |
| Citation enrichment (Semantic Scholar) | 16:31:01 | 16:31:12 | 11s | 1% |
| Store papers in the database | 16:31:12 | 16:31:13 | 1s | 0% |
| PDF download + Docling parsing | 16:31:13 | 16:35:16 | 4m 03s | 21% |
| Stage 3 preparation (aspect split, chunking, embedding) | 16:35:16 | 16:37:16 | 2m 00s | 10% |
| Stage 3 digest generation (Groq) | 16:37:16 | 16:37:23 | 7s | 1% |
| Stage 3 judge + coverage (per sub-question) | 16:37:23 | 16:39:48 | 2m 25s | 12% |
| Stage 4 fact check (claims, NLI, judges) | 16:39:48 | 16:47:58 | 8m 10s | 42% |
| **Total** | 16:28:35 | 16:47:58 | **19m 23s** | 100% |

Loop 2 (second search for uncovered aspects) is part of the judge + coverage phase above: 4s by its own step timings (0% of the run). Its searches, parses and filters are NOT counted in the retrieval figures of this report; it stored 0 new paper(s) and 0 new web page(s) with the run, so the stored counts of papers and web sources are higher than the log counts by these numbers.

## 3. Sub-questions: retrieval, filtering, parsing, Stage 3

| # | Sub-question | Pre-filter (cand. -> cleared -> shortlist) | Judge passed | Parsed full text | Web | Digests (full / abs / web) | Verified / total findings | Coverage |
|---|---|---|---|---|---|---|---|---|
| 1 | What is retrieval-augmented generation (RAG)? | 115 -> 114 -> 20 | 12 of 20 | 5 | 14 | 8 (5 / 0 / 3) | 32 / 33 | sufficient |
| 2 | What is fine-tuning? | 89 -> 71 -> 20 | 11 of 20 | 5 | 9 | 8 (5 / 0 / 3) | 26 / 26 | sufficient |
| 3 | What is domain knowledge? | 108 -> 72 -> 20 | 9 of 20 | 0 | 10 | 8 (0 / 5 / 3) | 10 / 11 | sufficient |
| 4 | How can RAG and fine-tuning be used to add domain knowledge to large language models? | 92 -> 90 -> 20 | 19 of 20 | 5 | 12 | 8 (5 / 0 / 3) | 30 / 32 | sufficient |
| 5 | How do RAG and fine-tuning compare in terms of performance, efficiency, and scalability for adding domain knowledge to large language models? | 71 -> 71 -> 20 | 11 of 20 | 5 | 10 | 8 (5 / 0 / 3) | 25 / 32 | sufficient |

- Relevance judge rejected 8 papers for [What is retrieval-augmented generation (]. Examples: 'Adaptive Control of Retrieval-Augmented Generation for Large' (The paper focuses on optimizing RAG performance rather than defining or explaining what RAG is.); 'A Comparison of Independent and Joint Fine-tuning Strategies' (The paper focuses on fine-tuning strategies for RAG rather than defining or explaining what RAG is.); 'Ragas: Automated Evaluation of Retrieval Augmented Generatio' (The paper focuses on evaluation metrics for RAG rather than explaining what RAG is.)
- Relevance judge rejected 9 papers for [What is fine-tuning?]. Examples: 'Fine-Tuning in Living Systems' (The paper discusses fine-tuning in biological and cosmological contexts rather than defining the general concept of fine-tuning in machine l); 'Fine Tuners' (The paper discusses industrial photopolymerization processes, not the machine learning concept of fine-tuning.); 'FINE-TUNING CAN DISTORT PRETRAINED FEATURES AND UNDERPERFORM' (The paper analyzes the effects and limitations of fine-tuning rather than defining or explaining what fine-tuning is.)
- Relevance judge rejected 11 papers for [What is domain knowledge?]. Examples: 'Wikipedia as domain knowledge networks: Domain extraction an' (The paper focuses on extracting and measuring domain knowledge networks rather than defining or explaining the concept of domain knowledge i); 'Measurement Issues in Knowledge Engineering' (The paper discusses factors affecting knowledge base quality in expert systems rather than defining the concept of domain knowledge itself.); 'Applying domain knowledge to the discovery of operating situ' (The paper discusses applying domain knowledge to a specific system rather than defining or analyzing the concept of domain knowledge itself.)
- Relevance judge rejected 1 papers for [How can RAG and fine-tuning be used to a]. Examples: 'Towards Understanding Systems Trade-offs in Retrieval-Augmen' (The paper focuses on system performance trade-offs and latency rather than the methods for integrating domain knowledge via RAG or fine-tuni)
- Relevance judge rejected 9 papers for [How do RAG and fine-tuning compare in te]. Examples: 'FedRAG: A Framework for Fine-Tuning Retrieval-Augmented Gene' (The paper focuses on federated learning architectures for RAG fine-tuning rather than comparing RAG and fine-tuning performance or scalabili); 'Finetune-RAG: Fine-Tuning Language Models to Resist Hallucin' (The paper focuses on improving RAG robustness against hallucinations via fine-tuning rather than comparing RAG and fine-tuning on performanc); 'Fine-tuning small language models for industrial retrieval-a' (The paper only evaluates fine-tuning and does not include a comparative analysis against RAG methods as required by the research question.)

### Sources behind each sub-question's digests

**1. What is retrieval-augmented generation (RAG)?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Research of Challenges and Solutions in Retrieval Augmented Generation (RAG) Systems | paper | full_text | 4 / 5 |
| A Survey on Retrieval-Augmented Text Generation for Large Language Models | paper | full_text | 5 / 5 |
| Direct Retrieval-augmented Optimization: Synergizing Knowledge Selection and Language Models | paper | full_text | 4 / 4 |
| Retrieval-Augmented Generation for AI-Generated Content: A Survey | paper | full_text | 4 / 4 |
| Retrieval-Augmented Generation: Methods, Applications and Challenges | paper | full_text | 5 / 5 |
| 5 key features and benefits of retrieval augmented generation (RAG) / The Microsoft Cloud Blog | web | web_snippet | 4 / 4 |
| What is RAG (Retrieval-Augmented Generation)? / Stanford HAI | web | web_snippet | 2 / 2 |
| What is RAG? - Retrieval-Augmented Generation AI Explained - AWS | web | web_snippet | 4 / 4 |

**2. What is fine-tuning?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Gauging fine-tuning | paper | full_text | 5 / 5 |
| Idling Neurons, Appropriately Lenient Workload During Fine-Tuning Leads to Better Generalizatio | paper | full_text | 0 / 0 |
| Naturalness and Fisher Information | paper | full_text | 4 / 4 |
| Partial Is Better Than All: Revisiting Fine-tuning Strategy for Few-shot Learning | paper | full_text | 4 / 4 |
| Which Fine-Tuning Failed? The Reported Failure and Recovery of Fine-Tuning in Model Editing Are | paper | full_text | 5 / 5 |
| A Comprehensive Introduction to Fine-Tuning LLMs | web | web_snippet | 5 / 5 |
| What is Fine-Tuning? / IBM | web | web_snippet | 2 / 2 |
| What is Fine-Tuning? / Stanford HAI | web | web_snippet | 1 / 1 |

**3. What is domain knowledge?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| An information model for managing domain knowledge via Faceted Taxonomies | paper | abstract | 0 / 1 |
| Assessing individual differences in knowledge: Knowledge, intelligence, and related traits. | paper | abstract | 2 / 2 |
| Domain Analysis | paper | abstract | 1 / 1 |
| Domain Knowledge | web | web_snippet | 2 / 2 |
| Domain Knowledge / Learn & Work Ecosystem Library | web | web_snippet | 1 / 1 |
| Domain Knowledge: Evolving Themes and Emerging Concerns | paper | abstract | 1 / 1 |
| Domain analysis in information science | paper | abstract | 1 / 1 |
| Domain knowledge - Wikipedia | web | web_snippet | 2 / 2 |

**4. How can RAG and fine-tuning be used to add domain knowledge to large language models?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| Fine Tuning vs. Retrieval Augmented Generation for Less Popular Knowledge | paper | full_text | 4 / 5 |
| Investigating the Performance of Retrieval-Augmented Generation and Domain-Specific Fine-Tuning | paper | full_text | 5 / 5 |
| RAFT: Adapting Language Model to Domain Specific RAG | paper | full_text | 4 / 4 |
| RAG vs Fine-tuning: Pipelines, Tradeoffs, and a Case Study on Agriculture | paper | full_text | 5 / 5 |
| RbFT: Robust Fine-tuning for Retrieval-Augmented Generation against Retrieval Defects | paper | full_text | 5 / 5 |
| Evaluating fine-tuning and retrieval-augmented generation for domain-specific language modeling | web | web_snippet | 3 / 4 |
| Fine Tuning vs. Retrieval Augmented Generation for Less Popular Knowledge / Proceedings of the  | web | web_snippet | 0 / 0 |
| What is retrieval-augmented generation (RAG)? - IBM Research | web | web_snippet | 4 / 4 |

**5. How do RAG and fine-tuning compare in terms of performance, efficiency, and scalability for adding domain knowledge to large language models?**

| Source | Type | Evidence | Verified / total findings |
|---|---|---|---|
| A Comparison of Independent and Joint Fine-tuning Strategies for Retrieval-Augmented Generation | paper | full_text | 5 / 5 |
| Fine-Tuning or Fine-Failing? Debunking Performance Myths in Large Language Models | paper | full_text | 3 / 5 |
| Medical LLMs: Fine-Tuning vs. Retrieval-Augmented Generation | paper | full_text | 4 / 5 |
| OPTIMIZING DOMAIN-SPECIFIC LARGE LANGUAGE MODELS: A COMPARATIVE ANALYSIS OF RETRIEVAL-AUGMENTED | paper | full_text | 5 / 5 |
| RAG vs Fine-tuning: Pipelines, Tradeoffs, and a Case Study on Agriculture | paper | full_text | 1 / 5 |
| Fine Tuning vs. Retrieval Augmented Generation for Less Popular Knowledge | web | web_snippet | 5 / 5 |
| RAG vs. Fine-tuning / IBM | web | web_snippet | 2 / 2 |
| [2403.09727] Investigating the performance of Retrieval-Augmented Generation and fine-tuning fo | web | web_snippet | 0 / 0 |

## 4. Stage 3: aspects and coverage

An aspect is covered when at least 2 judge "yes" verdicts come from at least 2 sources. States: covered, uncovered (judged, too few yes), no candidates, unjudged (a verdict failed).

### 1. What is retrieval-augmented generation (RAG)?

Sufficient: **True**; judge used: True; sources 8 (5 full text); judge candidates 18 = yes 13, partial 1, no 4, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How does RAG work? | covered | 5 | 4 |
| 2 | benefits of RAG | covered | 5 | 3 |
| 3 | challenges of RAG | covered | 3 | 2 |

### 2. What is fine-tuning?

Sufficient: **True**; judge used: True; sources 7 (4 full text); judge candidates 18 = yes 12, partial 2, no 4, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | How does fine-tuning work? | covered | 3 | 2 |
| 2 | benefits of fine-tuning | covered | 5 | 3 |
| 3 | challenges of fine-tuning | covered | 4 | 3 |

### 3. What is domain knowledge?

Sufficient: **True**; judge used: True; sources 7 (0 full text); judge candidates 11 = yes 9, partial 0, no 2, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | how domain knowledge is defined | covered | 5 | 4 |
| 2 | how domain knowledge is measured | covered | 3 | 3 |
| 3 | examples of domain knowledge for large language models | uncovered | 1 | 1 |

Uncovered details: What are some examples of domain knowledge for large language models?

Loop 2 (r1 triage, steps reselect, pool, queries): searched 0 aspect(s), covered 0 (0 by synthesis of several sources), sufficient True (strict rule: False), gap rule core, 0.0 s.

| Aspect | Status | Steps tried | Covered by | How | Before (yes/partial/no) | After (yes/partial, sources) |
|---|---|---|---|---|---|---|
| examples of domain knowledge for large language models | known_gap_no_evidence | - | - | - | 1/0/1 | 1/0, 1 |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|

### 4. How can RAG and fine-tuning be used to add domain knowledge to large language models?

Sufficient: **True**; judge used: True; sources 7 (5 full text); judge candidates 24 = yes 4, partial 8, no 12, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What are the methods for applying RAG and fine-tuning to domain-specific tasks? | uncovered | 0 | 0 |
| 2 | What are the frameworks for applying RAG and fine-tuning to domain-specific tasks? | covered | 2 | 2 |
| 3 | data requirements for RAG and fine-tuning | covered | 2 | 2 |
| 4 | computational requirements for RAG and fine-tuning | covered | 2 | 2 |

Uncovered details: What are the methods and frameworks for applying RAG and fine-tuning to domain-specific tasks?

Loop 2 (r1 triage, steps reselect, pool, queries): searched 0 aspect(s), covered 1 (1 by synthesis of several sources), sufficient True (strict rule: False), gap rule core, 4.1 s.

| Aspect | Status | Steps tried | Covered by | How | Before (yes/partial/no) | After (yes/partial, sources) |
|---|---|---|---|---|---|---|
| What are the methods for applying RAG and fine-tuning to domain-specific tasks? | known_gap_no_evidence | - | - | - | 0/1/5 | 0/1, 1 |
| What are the frameworks for applying RAG and fine-tuning to domain-specific task | covered | - | synthesis | synthesis | 0/4/2 | - |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|

### 5. How do RAG and fine-tuning compare in terms of performance, efficiency, and scalability for adding domain knowledge to large language models?

Sufficient: **True**; judge used: True; sources 7 (5 full text); judge candidates 27 = yes 11, partial 5, no 11, error 0; digest failures 0.

| # | Aspect | State | Yes verdicts | Sources |
|---|---|---|---|---|
| 1 | What metrics are used to evaluate RAG and fine-tuning for adding domain knowledge to large language models? | uncovered | 1 | 1 |
| 2 | What benchmarks are used to evaluate RAG and fine-tuning for adding domain knowledge to large language models? | uncovered | 1 | 1 |
| 3 | trade-offs of RAG and fine-tuning | covered | 3 | 3 |
| 4 | limitations of RAG and fine-tuning | covered | 4 | 4 |
| 5 | How do RAG and fine-tuning perform on different types of domain knowledge and tasks? | covered | 2 | 2 |

Uncovered details: What are the metrics and benchmarks for evaluating RAG and fine-tuning?

Loop 2 (r1 triage, steps reselect, pool, queries): searched 0 aspect(s), covered 0 (0 by synthesis of several sources), sufficient True (strict rule: False), gap rule core, 0.0 s.

| Aspect | Status | Steps tried | Covered by | How | Before (yes/partial/no) | After (yes/partial, sources) |
|---|---|---|---|---|---|---|
| What metrics are used to evaluate RAG and fine-tuning for adding domain knowledg | known_gap_no_evidence | - | - | - | 1/0/4 | 1/0, 1 |
| What benchmarks are used to evaluate RAG and fine-tuning for adding domain knowl | known_gap_no_evidence | - | - | - | 1/0/3 | 1/0, 1 |

| Step | Aspects | New sources | New verified findings | Covered | Seconds | Other |
|---|---|---|---|---|---|---|

## 5. Retrieval details

- Web search variants: [14, 9, 10, 12, 10] unique sources after de-duplication per sub-question (Tavily, 3 queries each, 5 results per query).
- Pre-filter lines: 115 candidates -> 114 cleared min_similarity (0.56) -> top 20 shortlisted; 89 candidates -> 71 cleared min_similarity (0.56) -> top 20 shortlisted; 108 candidates -> 72 cleared min_similarity (0.56) -> top 20 shortlisted; 92 candidates -> 90 cleared min_similarity (0.56) -> top 20 shortlisted; 71 candidates -> 71 cleared min_similarity (0.56) -> top 20 shortlisted
- Kept papers by source: {'openalex': 30, 'scopus': 22, 'arxiv': 4, 'both': 6}; requests to api.openalex.org in the log: 34
- Scopus: used
- Semantic Scholar: search skipped, probe failed - Semantic Scholar probe failed (HTTP 429): skipping Semantic Scholar search for this run; citation-enrichment batch calls answered 429: 0
- Citation enrichment: Citation enrichment: 4 arXiv-only papers to enrich; took 11s in total

## 6. Parsing details

- Attempted 31 papers, usable full text 20, 62 papers saved in the database.
- PDF obtained via: its own link: 13, Unpaywall: 2, the OpenAlex content API: 2; parse cache hits: 2; Unpaywall OA links found: 3; landing-page citation_pdf_url: 1
- Individual download failures: 18 -> HTTPStatusError: 11, ValueError: 7
- Headless-browser fallback: 9 tried, 9 failed; Docling fetch-by-URL attempts: 10; HTML full-text attempts that failed: 6

Papers with NO usable text from any route:

| Paper | Reason |
|---|---|
| Unveiling the Power of Large Language Models: A Comparative Study of Retrieval-Augmented G | all PDF routes failed: ValueError: ValueError('Non-PDF response (content-type: text/html) for https://doi.org/10. |
| Two Axes of Domains for Domain Analysis | all PDF routes failed: ValueError: ValueError('Non-PDF response (content-type: text/html) for http://hdl.handle.n |
| Domain Knowledge: Evolving Themes and Emerging Concerns | all PDF routes failed: HTTPStatusError: HTTPStatusError('403 Forbidden') |
| Domain analysis in information science | all PDF routes failed: HTTPStatusError: HTTPStatusError('403 Forbidden') |
| An information model for managing domain knowledge via Faceted Taxonomies | all PDF routes failed: ValueError: ValueError('Non-PDF response (content-type: text/html) for https://doi.org/10. |
| Domain Analysis | all PDF routes failed: ValueError: ValueError('Non-PDF response (content-type: text/html) for https://doi.org/10. |
| Assessing individual differences in knowledge: Knowledge, intelligence, and related traits | all PDF routes failed: HTTPStatusError: HTTPStatusError('403 Forbidden') |
| Measuring application domain knowledge: Results from a preliminary experiment | all PDF routes failed: None: None |
| Domain Analysis for Knowledge Organization: Tools for Ontology Extraction | all PDF routes failed: None: None |
| Quality measurement model for KADS-domain knowledge | all PDF routes failed: ValueError: ValueError('Non-PDF response (content-type: text/html) for https://doi.org/10. |

## 7. Groq and judge

- Stage 3: 40 digests for 5 sub-questions, 7 worker(s), 7 Groq key(s)
- Rate-limit parking events: 195; per key (events / parked seconds): ...3mla: 25 / 472s, ...Ef4D: 25 / 448s, ...KJJp: 31 / 520s, ...KaRe: 35 / 418s, ...X2Oj: 27 / 498s, ...uNUk: 26 / 456s, ...x1nP: 26 / 533s
- Judge batch latencies (s): [16.4, 16.6, 21.1, 21.4, 4.0, 24.8]

- Judge verdicts that came back as error: 0

## 7b. Stage 4: fact check

Claims after grouping: 97; labels {'unverified': 69, 'partially_supported': 22, 'supported': 6}; contradictions stored: 0; time 8m 10s.

| # | Sub-question | Digests | Claims | Clusters | Supported | Partly supported | Unverified | Contradicted |
|---|---|---|---|---|---|---|---|---|
| 1 | What is retrieval-augmented generation (RAG)? | 8 | 32 | 28 | 2 | 5 | 21 | 0 |
| 2 | What is domain knowledge? | 8 | 10 | 9 | 0 | 4 | 5 | 0 |
| 3 | What is fine-tuning? | 8 | 26 | 22 | 2 | 5 | 15 | 0 |
| 4 | How can RAG and fine-tuning be used to add domain  | 8 | 30 | 18 | 2 | 4 | 12 | 0 |
| 5 | How do RAG and fine-tuning compare in terms of per | 8 | 25 | 20 | 0 | 4 | 16 | 0 |

NLI pair cap: 138 quote/claim pairs passed the topic gate; only the 80 most similar go to NLI; 91 quote/claim pairs passed the topic gate; only the 80 most similar go to NLI

## 8. Warnings and errors in the log (grouped)

| Level | Count | Message (numbers, urls and titles replaced) |
|---|---|---|
| ERROR | 5 | All PDF URLs failed for <id>: ValueError: ValueError('Non-PDF response (content-type: text/html) for <url> |
| ERROR | 3 | All PDF URLs failed for <id>: HTTPStatusError: HTTPStatusError('<text>') |
| ERROR | 2 | All PDF URLs failed for <id>: None: None |
| WARNING | 11 | Failed to download from <url> HTTPStatusError: HTTPStatusError('<text>') |
| WARNING | 8 | Playwright fallback failed: ValueError: ValueError('<text>') |
| WARNING | 7 | Failed to download from <url> ValueError: ValueError('Non-PDF response (content-type: text/html) for <url> |
| WARNING | 2 | get_papers_for_stageN: database connection error (attempt N/N): RemoteProtocolError: Server disconnected |
| WARNING | 2 | Stage N: N quote/claim pairs passed the topic gate; only the N most similar go to NLI |
| WARNING | 1 | SN gave up on '<text>' after N attempts (last status N) |
| WARNING | 1 | Semantic Scholar probe failed (HTTP N): skipping Semantic Scholar search for this run |
| WARNING | 1 | Unpaywall route failed for '<text>': ValueError: Non-PDF response (content-type: text/html) for <url> |
| WARNING | 1 | Playwright fallback failed: TimeoutError: TimeoutError('<text>') |
| WARNING | 1 | database read failed (attempt N/N): RemoteProtocolError: Server disconnected |

## 9. Checks (rule based, from the log)

- Semantic Scholar search was skipped (probe returned 429).
- Sub-question 'What is domain knowledge?': no full-text digest (evidence is abstracts / web snippets only).
- 10 paper(s) could not be downloaded by any route.
- Groq rate limiting: 195 parking events; digest generation took 7s.
- Longest phase: Stage 4 fact check (claims, NLI, judges) (8m 10s, 42% of the run).

Warnings in the log: 35; errors: 10.

<!-- MANUAL NOTES (kept when this report is regenerated) -->

## 10. Notes

(write your reading of this run here)
