# Prompt for the frontend chat: written report v2 (collapsible evidence, a richer Answer, citations that open the parsed paper)

Copy everything below the line into the frontend chat. The backend part is done (commit message "Written report: citations, answer parts and finding ids"); the contract is in `docs/STAGE5_OUTPUT.md`, section "Added when the report is read (2026-11-19)".

---

You are working on the TRACE web app in `apps/web` (Next.js, App Router). Before you write code, read `apps/web/AGENTS.md` and the relevant guide in `node_modules/next/dist/docs/`: this Next.js version differs from what you know. Do not touch the backend (`apps/api`): if a field you need is missing, tell me what is missing instead of inventing it.

## What changes and why

The written report page (`app/research/[id]/written-report/page.tsx`, `components/ReportView.tsx`, view model in `lib/written-report.ts`, types in `lib/trace-types.ts`) shows the whole report as one long page. I want three changes:

1. **The extra content goes under collapse bars**, so the page opens on what matters.
2. **The Answer is the main thing on the page**: much more prominent and richer.
3. **A citation opens the paper page with the parsed content**, at the quote that the sentence is built on.

The backend now sends extra fields (all optional: when one is missing, show nothing, never an error, and keep working exactly as today). The server computes them when it reads the report, so they exist for every stored report, old runs too.

## The new fields of `GET /api/research/{id}/written-report`

Add these to `lib/trace-types.ts` (`WrittenSentence`, `WrittenReference`, `WrittenReport`, `PaperFinding`) and to the view model:

```ts
type Citation = { ref: number; paperId: string | null; parsed: boolean; quotes: CitedQuote[] }
type CitedQuote = { text: string; findingId: string; paperId: string | null; parsed: boolean; relation: 'supports' | 'near_match'; evidenceLevel: string | null }

// every sentence (overview.summary, sections[].sentences, conclusion) gets:
citations?: Citation[]                         // the verbatim quotes behind the sentence, grouped by reference; the reference numbers are exactly the sentence's refs; [] for a note

// every reference gets:
paper?: { id: string; parsed: boolean } | null   // the paper to open from the reference list; null for a web page
citedIn?: number                                  // in how many sentences of the report it is cited

// overview gets:
answer?: {
  headline: { sentenceIndex: number } | null       // the first statement of overview.summary: the verdict
  parts: { sentenceIndex: number; sectionId: string | null; title: string | null; sentence: WrittenSentence; supporting: WrittenSentence[] }[]
  strength: { statements: number; byTier: { supported: number; partly: number; single: number }; documents: number; fullTextDocuments: number
              documentsInReport: number | null; partsCovered: number; sections: number; disagreements: number; openQuestions: number; line: string }
  figures: { value: string; sentenceIndex: number; refs: number[] }[]     // percentages in the answer sentences (may be [])
  openQuestions: string[]                          // what the evidence does not settle
  disputes: { count: number; items: { sectionId: string; title: string; claimA: string; claimB: string; refs: number[] }[] }
}
```
And `GET /api/research/{id}/papers/{paperId}` now gives every finding an `id` (a string like `f_1a2b3c4d5e`). A citation's `quotes[].findingId` equals the `id` of a finding of the paper `quotes[].paperId` (the citation's own `paperId` is the paper of its first quote), so a citation can point at one highlighted quote.

Keep `lib/demo-written.ts` (demo mode) in step: add these fields to the demo report, with one parsed paper, one not-parsed paper and one web source, so every state below can be seen without the server. Keep the demo paper data (`lib/demo-papers.ts`) consistent with the new `findingId`s.

## 1. Collapse bars

Use a real disclosure pattern (a `<button aria-expanded aria-controls>` or `<details>`, like the `details.panel.fold` already used on the paper page), keyboard accessible, with the state visible on the bar. Style it like the existing `.fold` panels (`app/globals.css`), no new design language.

**Always visible, never collapsed** (these are rules of the report contract in `lib/written-report.ts`, keep them): the title and status, the warnings, the legend ("How to read the findings"), the Answer (change 2), the Limitations section, the "Sources disagree" blocks, and the tier label of every `partly` and `single` sentence.

**Under a collapse bar:**
- **Introduction**: collapsed by default (bar: "Introduction").
- **Each section of "Topic-wise Research Findings"**: collapsed by default. The bar shows the section title and its counts in words that do not claim more than the data (for example "12 findings · 2 partly supported · 5 one source, not confirmed · 1 disagreement"), taken from the section's own sentences and `counts`. A section that has a disagreement or gaps shows a small visible hint on the bar ("sources disagree" / "evidence gaps") so nothing important is hidden behind it. Opening it shows the detail questions, the sentences, the disagreements and the gaps, as today. Add one "Expand all / Collapse all" control for the sections.
- **Under every sentence, a small bar "Evidence (n)"**, collapsed by default, where n is the number of quotes in `citations`. Opened, it shows for each citation: the reference number and title (from `references`), the evidence hint when the source was read only in part ("abstract only", "web snippet" via `evidenceHint`), and the verbatim quotes (`quotes[].text`) as block quotes, with the label "supports" or "close variant (another document)" for `relation`. Each quote has the action "Open in the paper" (change 3). A sentence with no citations has no bar.
- **References**: the list stays at the end but under one bar ("References (27)"), collapsed by default; a click on a citation marker (change 3) must still be able to show a reference when it needs to (open the bar and scroll to it).
- The Conclusion stays visible.

Opening a bar must not move the page unexpectedly. Collapsed content must not be unreachable for screen readers: `aria-expanded` and `aria-controls`, and a visible focus style. Respect `prefers-reduced-motion`.

## 2. The Answer: highlighted and richer

Today the Answer (`overview.summary`) is 4 or 5 plain lines under a normal heading. Make it the hero of the page, using `overview.answer` (when it is missing, fall back to today's rendering of `overview.summary`):

- A prominent card at the top (below the legend), clearly different from the sections: stronger border or background, a larger type size, a title "Answer".
- **The headline**: the sentence `answer.headline.sentenceIndex` of `overview.summary` in a larger size, as the verdict. It keeps its citation markers and its tier label (a `partly` or `single` sentence is never styled like a confirmed finding, even in the hero).
- **The parts**: one block per `answer.parts[]`, titled with the part's `title` (the sub-question it comes from), containing its `sentence` (markers and tier label as everywhere) and, under a collapse bar "More on this part", its `supporting[]` sentences (each with its markers, tier label and its own "Evidence (n)" bar).
- **How well it rests on the evidence**: a compact strip made from `answer.strength`: show `strength.line` as it is (the server wrote it; do not reword it, do not add a verdict such as "reliable" or "strong") and the numbers as small figures: documents behind the answer (and how many were read in full text), parts covered of sections, and counts by tier. A small bar split by tier (`supported`, `partly`, `single`) is welcome; the colours must keep the distinction that the sentence borders already have, and the numbers must be readable without colour.
- **Key figures**: `answer.figures[]` as chips ("35%"), each linking (scroll) to its sentence; leave the block out when it is empty.
- **What is still open**: `answer.openQuestions[]` as a short list under "The evidence does not settle", and `answer.disputes` as a visible line "N disagreements between sources" with the first items (their `title` and the two claims) and a link that scrolls to the "Sources disagree" block of that section (open the section's bar first). This block is always visible, not collapsed.
- Keep the counts row (`overview.counts`) but move it under the Answer card as secondary information.
- The legend stays above the Answer, and the sentence "This report is not a verified answer" (`notVerified`) stays visible near it.

Do not change any wording of the report text itself, and do not hide or soften the labels. The Answer must look important, not more certain than it is.

## 3. Citations open the parsed paper

Today a marker `[3]` is an anchor to the reference list. Change it so that a click opens the page of the paper, and keep the old behaviour as the fallback:

- A marker is built from the sentence's `citations`: for a citation with a `paperId`, the marker is a link to `/research/{runId}/papers/{paperId}?finding={quotes[0].findingId}&from=written-report`. Use the router's `Link` (same tab; the paper page has a way back, see below). Its title/tooltip: the reference title plus "Open the parsed paper" (or "Open the paper (not parsed: abstract and findings only)" when `parsed` is false).
- A citation with `paperId: null` (a web source): the marker opens the reference's `url` in a new tab (`rel="noopener noreferrer"`, only http/https via the existing `safeUrl`), with the tooltip "Open the web page (no parsed copy)". If there is no url, fall back to the anchor of the reference in the list (open the References bar first).
- A marker with no `citations` entry (an old report, or a failed server step): the anchor to the reference, as today.
- A keyboard user must reach every marker; each marker has an `aria-label` such as "Reference 3: <title>, open the parsed paper".
- In the reference list, each reference with `paper` gets the actions "Open parsed paper" (link as above, without `finding`) and, when it has a url, "Open source". A reference with `paper: null` only has "Open source".
- In the "Evidence (n)" bar, each quote has "Open in the paper": `/research/{runId}/papers/{quote.paperId ?? citation.paperId}?finding={quote.findingId}&from=written-report`.

**The paper page** (`app/research/[id]/papers/[paperId]/page.tsx`, `components/trace/parsed-text.tsx`) already shows the parsed text with the quotes highlighted and a "Show in the parsed text" button per finding. Add:
- Read the query parameter `finding`. When the paper has a finding with that `id`, then once the parsed text is rendered: scroll the "Parsed content" section into view, set that finding active (the same as the "Show in the parsed text" button does: `setActive(i)` and `text.current?.jumpToMark(i)`), and make it clear which quote was asked for (a visible line above the parsed text: "Opened from the written report: this is the quote behind the citation", with a button to clear the highlight). If the finding exists but its `spans` is empty (the quote could not be located), say so in words and show its quote text instead; never highlight a guessed place. If no finding has that id, open the page normally and show a one-line note.
- Read `from=written-report`: the "Back to the run" link at the top becomes "Back to the written report" (`/research/{runId}/written-report`) and keeps the scroll position of the report where possible (a plain back navigation is enough). Without `from`, keep the existing link.
- A paper that was not parsed (`parsed` false or `paper.parse.status !== 'parsed'`) keeps today's amber notice; show the abstract and the findings, and open the finding's quote text in the findings list. Do not pretend there is a parsed text.
- Make the "Parsed content" section easy to find when arriving from a citation: it should not sit behind a long list of findings; the quote asked for is shown first in the findings list when `finding` is set.

## Rules that must keep holding (from `lib/written-report.ts`)

Every `partly` and `single` sentence carries its label wherever it is shown, including the hero, the parts, the supporting sentences and the Evidence bars; a `note` sentence has no label and no markers; the legend, the limitations and the status are always visible; disagreements show both sides with their quotes and never say that one side is false; a missing field shows as nothing; text from the server is never put in a link unchecked (`safeUrl`); no new dependency unless it is clearly needed.

## Tests and checks

- Extend `tests/written-report.test.ts` (pure functions, `pnpm test`): the view model builds the marker links from `citations` (paper link with `finding`, web link, fallback anchor), the section bar summary, the answer view with and without `overview.answer`, and every tier-label rule in the new places.
- `pnpm typecheck` and `pnpm test` must pass, and the page must build (`pnpm build`).
- Check in the browser with the demo mode (all states: parsed paper, not parsed paper, web source, report without the new fields, a report with a disagreement and with gaps) and, when the API is running, with the run `ea6c6f82-3b3c-4d88-828d-61b446a257ff`. Check at a narrow (phone) width, with the keyboard only, and with the browser set to reduced motion.
- Do not "correct" the backend. If something does not match this description, report exactly what you saw (the field, the run id, the response) and stop there.
