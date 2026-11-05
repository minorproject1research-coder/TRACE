# Report 11 - Aspect-splitter prompt test (NOT adopted)

**Question.** The central question of the Mamba run ended with an aspect that asks for results on two dimensions at once ("... in training efficiency AND long-sequence performance"). V2 judged most claims "partial" because each covers only one half. Would a splitter prompt that also splits separate dimensions fix this without hurting other details?

**Method** (`tests/aspect_split_prompt_test.py`, real Groq calls, no database or aspect-cache writes). All 91 compound detail questions among the 115 distinct stored ones (those containing and / or / vs / compare / a comma; the others cannot change). OLD = the current prompt, NEW = a variant that adds "split separate dimensions, criteria or metrics" with examples ("compare X with Y in training efficiency and long-sequence performance", "impact on speed and memory") and keeps the "do not split" rules for entity pairs, "e.g." lists, one concept and near-synonyms. 222 calls (91 x 2 + 40 repeats of OLD to measure noise). The decision rule was written before the first run: adopt only if at least 75% of the changes are judged good splits (judged blind, lists shown as A/B in random order) and the share of changed details exceeds the OLD-versus-OLD share by at least 10 points.

## Result

| | OLD | NEW |
|---|---|---|
| Details with 1 / 2 / 3 aspects | 35 / 53 / 3 | 11 / 74 / 6 |
| Detail questions whose aspect count differs | 25 of 91 (27%) | (all 25 are splits into more aspects, none into fewer) |
| Noise: OLD versus OLD, same prompt twice | 3 of 40 (8%) | |

- Criterion (b) passes: 27% against 8% noise, a gap of 19 points.
- Criterion (a) fails: judged blind, NEW's list was better in **4 of 25** changed cases (16%), OLD's in 20, one tie. The rule needed 75%.

**Where NEW was better (4):** "type, quality and relevance of documents, the prompt, and the model architecture" (3 separate factors); "quality and relevance of the input data"; "quality and diversity of training data"; and the Mamba case that motivated the test ("empirical results ... in training efficiency and long-sequence performance" -> one aspect per dimension).

**Where NEW was worse (20), by type:**
- "A or B" alternatives split into two required aspects (trade-offs or challenges; error cases or mismatches; empirical evidence or benchmarks; metrics or benchmarks; tasks that require or benefit): 8 cases. "Or" means either is enough, and splitting turns it into both.
- Comparisons split into "X" and "the others" (speculative decoding versus other methods: 5 cases), which destroys the comparison.
- Near-synonyms split (degrade or fail, fact-checking and verification, dependencies and relationships, mechanisms or factors, reduce or increase): 5 cases.
- An entity pair split although the prompt said not to (LoRA and full fine-tuning), an "e.g." list turned into required sub-aspects, and a case where the split dropped the qualifier ("theoretical explanations"): 3 cases.

## Decision
Do not change the splitter prompt. The cases it improves are the same shape as the ones it damages ("A and B" joining dimensions versus joining synonyms), and the 9B-class model cannot tell them apart reliably. A narrower prompt (only "and", never "or", never comparisons) would be a new prompt tuned on these results and would need fresh details to test it on.

## What this means for the central question
The two-part aspect remains. Options, none done: (1) accept it: "not sufficient" is then a conservative but honest answer, and Loop 2 is the place to look for the missing half (it can search for each dimension separately); (2) relax V2's "one half of a two-part aspect is partial" clause, which needs its own held-out test; (3) split only when the aspect text itself lists dimensions with "and" and a comparison partner, by a rule in code rather than a prompt. Option 1 is the cheapest and the one I would take.

Files: `reports/aspect_split_prompt_test.json` (all outputs), `reports/aspect_split_prompt_key.json` (A/B key), `reports/aspect_split_judgments.json` (my blind judgments; one LLM judge, 25 cases).
