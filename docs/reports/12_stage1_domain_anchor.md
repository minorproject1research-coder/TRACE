# Report 12 - Stage 1 domain anchor (keeping the field of the question in the searches)

**Problem.** The fine-tuned planner writes generic background sub-questions and queries ("What are transformers and how do they work?", "transformers overview", "state space models overview"). The original question never reaches Stage 2, so a search engine returns electrical-power transformers and statistical / econometric state-space models, and the relevance judge, which sees only the sub-question, has no way to know they are the wrong field. In two runs of the Mamba question this left sub-question 2 with 0-1 papers and sub-question 1 "sufficient" on econometrics and ecology papers.

**Constraint.** The planner is a fine-tuned LoRA model; its input/output format is fixed, so it is not changed. The fix is applied around it.

## Design (`apps/api/agents/stage1_planner/domain_anchor.py`, switch `DOMAIN_ANCHOR`, default on)
One LLM call per question (Groq gpt-oss, temperature 0, cached per question so a rerun searches the same way) returns
- `anchor`: 1-3 words naming the intended field ("deep learning"), appended to every search query (papers and web) unless the query already contains those words, and added to the text the embedding pre-filter compares with the abstracts;
- `context`: one sentence naming the field and the intended meaning of ambiguous terms, appended to the sub-question text the relevance judge sees (`... [Field: ...]`). No host change: the judge prompt is unchanged.

Both are empty when the call fails (the pipeline then behaves as before). The anchor is held in memory on the task plan (no database column) and logged (`Domain anchor: ...`); the run report shows it.

## What the experiments showed (retrieval and judge only, real search APIs, no parsing)

| Variant | Transformers sub-question | State-space sub-question |
|---|---|---|
| Today (no anchor) | top 20 = about 17 electrical-power papers; judge passes 0-1 | top 20 = SSpace toolbox, State Space Models in R, ecology, econometrics; judge passes 10, all statistical |
| Anchor "deep learning" in queries + pre-filter, judge sees the field context (**built**) | top 20 = neural-network transformers (3 power-transformer papers with deep learning remain); judge passes 8, all neural | pool of deep-learning state-space models; judge passes 6: Linear State-Space Layers, Simple Discrete State Spaces, Vision Mamba survey, structured SSMs as deep Wiener models |
| Anchor "machine learning" (what the model first produced) | 11 of 20 are power-transformer fault-prediction papers: too broad | still mixed with variational / Gaussian-process state-space models |
| Append a word from the question ("Mamba") to the queries | the transformers question returns only Mamba papers: steers too hard | all Mamba papers, S4 and the foundations disappear |
| No anchor, rank by sub-question + original question, judge sees the original question | transformers fixed (20 of 20 neural); judge 6 | about half deep learning; judge 7 (5 deep learning, 2 statistical) |
| Adding the original question to the pre-filter text on top of the built design | passes 10 but drifts to application papers (agriculture, news, trading) | passes 8 (adds Simplified State Space Layers) |

Judge context compared on the built pools: field context sentence passes 8 / 6, original question only 5 / 11, both 6 / 5. The field context was the best fit for the question's intent (it excludes electrical transformers and control-theory state-space models explicitly).

**Getting the model to choose the anchor.** The first prompt leaked its own example sentence into unrelated questions (the RAG and quantization questions got "not electrical transformers or statistical state-space models"). A prompt that asks for reasoning first produced random single words ("neural", "weights", "function"). The final prompt shows five worked examples from unrelated questions (two ambiguous with different outcomes, one for a battery cell, two unambiguous), asks for the narrowest field that excludes the other meaning, and was checked on 16 questions: Mamba and long-context transformers -> "deep learning", power-grid transformers -> "electrical engineering", CAR-T cell -> "immunotherapy", attention in psychology -> "human cognition", no stray single words.

**Harm check on questions that were already fine** (speculative decoding, RAG and hallucination): the shortlist changes (9 and 13 of 20 papers shared with the baseline) but both lists are entirely on-topic; the anchor surfaces different good papers, not worse ones.

## Known weaknesses
- The anchor model over-flags ambiguity: unambiguous questions still get a broad anchor ("NLP", "machine learning") and a context with needless negations ("RAG ... not a red-amber-green rating system"). Harmless in the checks above, but noise.
- Still imperfect: 3 of 20 transformer shortlist papers are power transformers with deep learning in the title; the state-space shortlist holds mostly latent-variable "deep state-space models", not only the S4/Mamba line, so S4-type background papers are still a minority.
- The planner is not deterministic (sub-questions 4 and 5 differed between the two runs), so the anchor only fixes the searches, not the wording of the sub-questions.
- Verified offline and with real search APIs, not yet in a full pipeline run.

## How to check the next run (question 1)
Run report row "Domain anchor"; sub-question 2 should have several papers that passed the judge (it had 0-1), sub-question 1 should have deep-learning state-space papers in its "Sources behind each sub-question's digests" table, and the number of parse failures from statistics / ecology papers should drop to zero.
