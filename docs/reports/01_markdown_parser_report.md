# Report 1 - Markdown parser rewrite (Stage 2 paper parsing)

Date: 2026-10-11. Scope: how Docling's Markdown is turned into title / authors / abstract / sections / references,
what was wrong, what was changed, and how well the new version works.

Files: `apps/api/agents/stage2_retrieval/markdown_parser.py` (new), `paper_retrieval_agent.py` (`_parse_with_docling`,
`_apply_metadata`), `scripts/backfill_parsed_papers.py` (new), `db/migrations/009_add_parser_version_and_cache_indexes.sql` (new).

## 1. Why this was looked at

The `parsed_papers` table showed papers whose abstract was mixed into the author field. The audit covered the 18 rows
stored by the RAG run (query `e1b91c81`): 3 were empty (Docling returned nothing), 15 had text.

Stage 3 reads only `sections` and `full_text`; the parsed `title`, `authors` and `abstract` are not consumed there.
So the section bug mattered for quality, and the author / abstract / title problems were cosmetic today but would
surface in Stage 4/5 citations.

## 2. What was wrong (15 papers with text)

| Field | Problem | Papers |
|---|---|---|
| Authors | abstract text, keywords or journal headers stored as author names (17 to 136 "authors" each) | 6 |
| Authors | none found | 2 |
| Authors | marker symbols left in (`Yue Zhang ♠∗`), two names merged, or only 1 of 4 found | about 5 |
| Authors | clean | about 3 |
| Abstract | leading dash from `Abstract - ...` | 4 |
| Abstract | runs of spaces from the PDF text | 4 |
| Abstract | stray "Review Article" prefix | 1 |
| Abstract | empty (no "Abstract" label) | 1 |
| Title | journal name taken as the title | 1 |
| Sections | author / affiliation / running-header lines became section headings | 6 |
| Sections | figure text became headings (`User Input`, `Caption 1:`, `where:`, `Docstring`) | 3 |
| Sections | **zero text in all 49 sections** (236,865-character survey) | 1 |
| References | 0 found although the paper has some (2 for a 160k-character survey) | 4 |

## 3. Root causes (old inline loop in `_parse_with_docling`)

1. **Authors**: every line after the title was collected as an author line until a word like "university" appeared. A
   paper with an inline `Abstract. ...` paragraph and no affiliation line before it had its abstract collected as authors.
2. **Abstract**: only a `## Abstract` heading was recognised. The fallback regex kept the leading dash and double spaces,
   and papers without an "Abstract" label got nothing.
3. **Title**: the first `#`/`##` line was the title, which for journal templates is the journal name.
4. **The bug that wiped the sections**: `in_references` was set True by any heading containing "reference" and was
   never reset. The Cheng survey has `## ACMReference Format:` right after its abstract, so every later section was
   treated as references and lost its text (49 sections, 0 characters). "Preference" headings would also trigger it.
5. **Heading noise**: every `##`/`###` line became a section, including author lines, page headers and figure labels.

## 4. What was changed

### 4.1 New module `markdown_parser.py` (pure functions, no I/O)
`parse_markdown(md) -> ParsedMarkdown(title, authors, abstract, sections, references)`.

- **Title**: first heading that is not a journal header, figure label, known section name or ACM boilerplate.
- **References**: only a real References / Bibliography / Works Cited heading (or a plain line saying exactly that)
  starts the reference list. An appendix heading ends it. Headings inside the list are ignored. One entry per
  non-trivial line (25+ characters), at most 1000.
- **Section headings** are accepted when numbered (`1`, `2.1`, `I.`, `A.`) or a known name (Introduction, Methods,
  Results, Conclusion, ...). Otherwise they are rejected if they: start lowercase (sentence fragments), look like a
  figure label (`Caption`, `Figure`, `Table`, `Algorithm`, `Video content`), contain affiliation or journal words
  (university, institute, ISSN, vol., doi, ...), repeat an earlier unnumbered heading (running page header), or - in the
  front matter only - look like a list of person names. Rejected headings stay as ordinary text.
- **Post-pass**: an unnumbered "section" with under 60 characters of text, or a name-like heading with under 300
  characters, is folded into the previous section.
- **Abstract**, in order: a `## Abstract` heading; an inline `Abstract - ...` / `Summary:` paragraph in the front
  matter; otherwise the first prose paragraph of 400+ characters. Leading dashes and "Review Article" prefixes are
  removed and whitespace collapsed.
- **Authors** (fallback only): short name-like lines between the title and the abstract / first section, marker
  symbols stripped, at most 40.
- **Levels**: taken from the numbering (`2.1` is level 2) instead of always 1.
- `PARSER_VERSION = 1` is defined here; bump it when the rules change in a way that makes stored rows worse than a
  fresh parse.

### 4.2 `_parse_with_docling` and API metadata
The inline loop is replaced by a call to `parse_markdown`. A new `PaperRetrievalAgent._apply_metadata` runs wherever a
Docling result is stored (three places): title, authors and abstract from the API metadata (OpenAlex / arXiv / S2)
**win** over the PDF-derived values, which only fill gaps. Sections, references and full text always come from the
parse. The metadata abstract is used when it has 100+ characters.

### 4.3 Related additions
- Migration 009 adds `parsed_papers.parser_version` and lookup indexes (used by the parse cache, see report 2).
- `scripts/backfill_parsed_papers.py` re-parses the stored Markdown of old rows with the current parser, without
  Docling or downloads, and stamps them.

## 5. Results (offline re-parse of the same 15 papers' stored Markdown)

| Check | Before | After |
|---|---|---|
| Authors polluted with abstract / keywords / journal text | 6 papers | 0 in stored data (metadata authors win); the parser's own fallback is clean on most papers |
| Abstract with leading dash / extra spaces / empty | 9 | 0 |
| Journal name as title | 1 | 0 |
| Cheng survey: text inside sections | 0% | 63% |
| Author / affiliation lines as headings | 6 papers | 1 left ("Neil Roy") |
| Figure labels as headings | 3 papers | 1 left ("Hallucination Explanation") |
| Papers with 0 references found | 4 | 0 |

Per paper (sections / references, old to new):

| Paper | Sections | References |
|---|---|---|
| Gu, Challenges and Solutions in RAG | 13 -> 12 | 16 -> 16 |
| Ahmadi, Mysteries of Hallucination | 25 -> 24 | 72 -> 72 |
| Cheng, Knowledge-Oriented RAG survey | 49 -> 49 (0 -> 63% text) | 323 -> 339 |
| Zhang, Siren's Song survey | 31 -> 29 | **2 -> 253** |
| Lamba, Lifecycle-Based survey | 46 -> 42 | 141 -> 151 |
| Zhang, Hallucinations in code generation | 20 -> 20 | 79 -> 81 |
| Gupta, RAG and Hallucination overview | 7 -> 6 | **0 -> 16** |
| Xie, Ensemble Voting | 17 -> 16 | 48 -> 49 |
| Rathod, Efficient Usage of RAG | 9 -> 5 | 12 -> 12 |
| Dimitrova, RAG: Advances and Challenges | 16 -> 16 | 38 -> 38 |
| Sunil, Mapping the RAG landscape | 33 -> 31 | 346 -> 346 |
| Kumar, Improving Reliability of LLMs | 34 -> 30 | **0 -> 14** |
| Elchafei, Facet-Level Tracing | 58 -> 21 | 13 -> 111 |
| Ye, Cognitive Mirage | 8 -> 7 | 5 -> 176 |
| Rawte, Hallucination in Foundation Models | 20 -> 17 | **0 -> 42** |

The share of full text inside sections went down for some papers (for example 86% -> 79%) because references and
front matter are now correctly kept out of the sections.

### Confirmation on a fresh run (speculative-decoding query, 16 parsed papers)
Authors clean, abstracts without dashes or extra spaces, every paper with text having 50 to 86% of it in sections, and
20 to 243 references each. Remaining visible leftovers: a bare `5` heading in one survey, a repeated title as the first
section of one tutorial paper, and source-metadata glitches (`stn, Ahmet`) that come from the API, not the parser.

## 6. Known limitations

- **Heuristic, English-only**: the rules assume numbered or conventionally named sections. A paper with unnumbered,
  non-standard headings relies on the repeat / lowercase / tiny-section filters.
- **Two stray headings remain** in the audited set ("Neil Roy", "Hallucination Explanation"); they are
  indistinguishable from real headings by rule.
- **Author fallback** can still pick up fragments (for example an address, "Computer Science", or a single first
  name). It only matters when the APIs return no authors.
- **Docling failures are not parser failures**: 3 of 18 papers in the audited run returned empty content.
- **Tables, equations, two-column ordering** are whatever Docling's Markdown gives; the parser does not repair them.
- **No automated tests in the repo yet.** The checks above were run from scratch scripts against stored full texts.
  A regression test with a few saved Markdown fixtures is the obvious next step.

## 7. How to extend

Add a fixture (the saved `full_text`) when a new failure pattern appears, adjust a rule in `markdown_parser.py`, bump
`PARSER_VERSION`, and run `scripts/backfill_parsed_papers.py` so old rows are rebuilt and become cacheable again.
