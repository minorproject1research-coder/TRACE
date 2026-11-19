// Run with:  pnpm test. The written report (Stage 5): markers and tier labels, status, disagreements, tolerance, the 202 / 404 / generate states, the report stage.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { demoApi, demoEvents } from '../lib/demo-api'
import { demoWrittenResponse } from '../lib/demo-written'
import { REPORT_NOT_RUN, stageMeta, stageStateLabel, stageStateWord } from '../lib/format'
import { notesOf } from '../lib/stream'
import { buildTimeline, reportLane } from '../lib/timeline'
import { noteView } from '../lib/telemetry'
import type { WrittenReportResponse } from '../lib/trace-types'
import { demoDetail } from '../lib/demo-papers'
import {
  downloadName, evidenceHint, generateMessage, LEGEND, markerFor, markers, paperHref, PARTLY_LABEL, refFor, reportModel, safeUrl, sectionSummary, sentenceParts, SINGLE_LABEL, statusView, tierView, writtenReportButton,
  type SentenceView,
} from '../lib/written-report'

const kinds = ['completed', 'warnings', 'insufficient'] as const
const sentencesOf = (res: WrittenReportResponse) => [...(res.report.overview?.summary ?? []), ...(res.report.sections ?? []).flatMap(s => s.sentences ?? []), ...(res.report.conclusion ?? [])]

// ------------------------------------------------------------------------------------------------------------------------ markers
test('the markers are the numbers of refs in one pair of brackets, joined with ", ", before the final full stop', () => {
  assert.equal(markers([1, 3]), '[1, 3]'); assert.equal(markers([2]), '[2]'); assert.equal(markers([]), ''); assert.equal(markers(undefined), ''); assert.equal(markers(['x', 4, NaN]), '[4]')
  const p = sentenceParts({ text: 'Two sources report that X.', refs: [1, 3] })
  assert.deepEqual([p.body, p.stop, p.refs], ['Two sources report that X', '.', [1, 3]])
  assert.equal(`${p.body} ${markers(p.refs)}${p.stop}`, 'Two sources report that X [1, 3].')
  assert.deepEqual(sentenceParts({ text: 'No final stop', refs: [2] }), { body: 'No final stop', stop: '', refs: [2] })
  assert.equal(sentenceParts({ text: 'It cost 3.5 times more, e.g. in production.', refs: [1] }).body, 'It cost 3.5 times more, e.g. in production')
  assert.deepEqual(sentenceParts({ text: '', refs: undefined }), { body: '', stop: '', refs: [] })
})

test('every sentence of the demo reports: the text has no marker, and every marker points to the reference with that number', () => {
  for (const kind of kinds) {
    const res = demoWrittenResponse(kind)
    const refs = res.report.references ?? []
    assert.deepEqual(refs.map(r => r.number), refs.map((_, i) => i + 1), 'numbers are 1-based and contiguous')
    for (const s of sentencesOf(res)) {
      assert.ok(!/\[\d+(, \d+)*\]/.test(s.text), `the text of a sentence never contains a marker: ${s.text}`)
      for (const n of s.refs ?? []) assert.equal(refFor(refs, n)?.number, n, `marker ${n} of "${s.text}"`)
    }
    const m = reportModel(res)
    // without a run id there is nothing to open a paper in, so a marker with a paper is the anchor of its reference; a web source opens its url (new tab)
    for (const v of [...m.summary, ...m.sections.flatMap(x => x.sentences), ...m.conclusion]) for (const l of v.links) {
      assert.ok(l.found, `reference ${l.n} exists`); assert.ok(m.references.some(r => r.anchor === `ref-${l.n}`))
      if (l.kind === 'anchor') assert.equal(l.href, `#ref-${l.n}`); else assert.equal(l.kind, 'web')
    }
  }
  assert.equal(refFor([{ number: 2 }, { number: 5 }], 5)!.number, 5); assert.equal(refFor([{ number: 1 }], 9), null); assert.equal(refFor(undefined, 1), null)
})

// ------------------------------------------------------------------------------------------------------------------------ tiers
test('tier partly always says "partly supported"; tier single always says "one source, not confirmed" and never looks confirmed; an unknown tier is not confirmed either', () => {
  assert.equal(tierView('partly').label, 'partly supported'); assert.equal(PARTLY_LABEL, 'partly supported')
  assert.equal(tierView('single').label, 'one source, not confirmed'); assert.equal(SINGLE_LABEL, 'one source, not confirmed')
  assert.equal(tierView('supported').label, null); assert.equal(tierView('supported').tone, 'mint')
  for (const t of ['partly', 'single', 'mystery', '', null, undefined]) assert.notEqual(tierView(t as string).tone, 'mint', String(t))
  assert.match(tierView('mystery').label!, /mystery.*not confirmed/); assert.equal(tierView(undefined).label, SINGLE_LABEL, 'no tier at all: treated as one source')
  assert.equal(tierView(' PARTLY ').kind, 'partly', 'case and spaces do not matter')
})

test('every partly and single sentence of every demo report carries its label, in the view and in the Markdown', () => {
  for (const kind of kinds) {
    const res = demoWrittenResponse(kind)
    const m = reportModel(res)
    const views = [...m.summary, ...m.sections.flatMap(x => x.sentences), ...m.conclusion]
    for (const v of views) {
      if (v.tier.kind === 'partly') assert.equal(v.tier.label, 'partly supported')
      if (v.tier.kind === 'single') assert.equal(v.tier.label, 'one source, not confirmed')
      if (v.tier.kind !== 'supported' && v.tier.kind !== 'note') assert.ok(v.tier.label, 'a sentence that is not supported always has a label (a plain note has none)')
    }
    const all = sentencesOf(res)
    const count = (t: string) => all.filter(s => s.tier === t).length
    assert.equal((res.markdown.match(/\*\(partly supported\)\*/g) ?? []).length, count('partly'))
    assert.equal((res.markdown.match(/\*\(one source, not confirmed\)\*/g) ?? []).length, count('single'))
    if (kind !== 'insufficient') assert.ok(count('partly') > 0 && count('single') > 0)
  }
})

// ------------------------------------------------------------------------------------------------------------------------ status, legend, limitations
test('the status chip: completed, completed_with_warnings, insufficient_evidence and failed are visible states; an unknown one shows its word', () => {
  assert.equal(statusView('completed').note, null); assert.equal(statusView('completed').tone, 'mint')
  const w = statusView('completed_with_warnings'); assert.equal(w.label, 'Completed with warnings'); assert.equal(w.tone, 'amber'); assert.match(w.note!, /Warnings/)
  const i = statusView('insufficient_evidence'); assert.equal(i.label, 'Insufficient evidence'); assert.match(i.note!, /insufficient for a written answer/)
  const f = statusView('failed'); assert.equal(f.isError, true); assert.equal(f.tone, 'coral'); assert.match(f.note!, /evidence report is still available/)
  const u = statusView('brand_new_status'); assert.equal(u.label, 'brand new status'); assert.equal(u.known, false); assert.equal(statusView(undefined).label, 'Unknown status')
})

test('the legend is always there, the limitations are never dropped, and the warnings of a report with warnings are listed', () => {
  for (const kind of [...kinds, 'failed'] as const) {
    const m = reportModel(demoWrittenResponse(kind))
    assert.equal(m.legend, LEGEND); assert.doesNotMatch(m.legend, /Two sources report/); assert.match(m.legend, /without a label is stated by two or more documents/); assert.match(m.legend, /close variant in another/); assert.match(m.legend, /partly supported/); assert.match(m.legend, /not confirmed/)
    assert.ok(m.limitations.length > 0, kind + ': limitations are listed'); assert.match(m.notVerified, /not a verified answer/)
  }
  const warn = reportModel(demoWrittenResponse('warnings'))
  assert.equal(warn.status.label, 'Completed with warnings'); assert.equal(warn.warnings.length, 3); assert.ok(warn.limitations.some(l => /template wording/.test(l)))
  assert.ok(warn.limitations.some(l => /not reviewed by a person/.test(l)), 'the standing caveat about the conflict check')
  assert.equal(reportModel(demoWrittenResponse('completed')).warnings.length, 0)
  const ins = reportModel(demoWrittenResponse('insufficient')); assert.equal(ins.empty, true); assert.equal(ins.status.label, 'Insufficient evidence'); assert.ok(ins.sections.every(s => s.gaps.length > 0))
  const failed = reportModel(demoWrittenResponse('failed')); assert.equal(failed.status.isError, true); assert.ok(failed.warnings.length > 0 && failed.limitations.some(l => /failed/i.test(l)))
})

test('the order of the blocks and the counts of the overview', () => {
  const m = reportModel(demoWrittenResponse('completed'))
  assert.deepEqual(m.sections.map(s => s.id), ['sec-1', 'sec-2', 'sec-3', 'sec-4']); assert.equal(m.introduction.length, 2); assert.ok(m.conclusion.length > 0)
  assert.deepEqual(m.counts.map(c => c.label).slice(0, 6), ['sections', 'documents', 'claims', 'supported', 'partly supported', 'one source, not confirmed'])
  assert.equal(m.counts.find(c => c.key === 'references')!.value, 6)
  assert.ok(m.sections[0].detailQuestions.length > 0); assert.equal(m.sections[2].sentences.length, 0); assert.ok(m.sections[2].gaps.length > 0)
})

// ------------------------------------------------------------------------------------------------------------------------ disagreements, references
test('disagreements show both sides with the quote and the reference, and never say that one side is false', () => {
  const m = reportModel(demoWrittenResponse('warnings'))
  const d = m.sections[0].disagreements[0]
  assert.ok(d.claimA && d.claimB && d.sideA.quote && d.sideB.quote)
  assert.deepEqual([d.sideA.marker?.n, d.sideB.marker?.n], [4, 5]); assert.ok(d.sideA.marker!.found && d.sideB.marker!.found)
  const text = [d.claimA, d.claimB, d.note, d.sideA.quote, d.sideB.quote, d.sideA.title, d.sideB.title].join(' ')
  assert.ok(!/\b(false|wrong|incorrect|untrue)\b/i.test(text), text); assert.match(d.note!, /does not decide/)
  const bare = reportModel({ status: 'completed', report: { sections: [{ title: 'S', disagreements: [{ claimA: 'a', sideA: { quote: 'q' } }] }] } })
  assert.equal(bare.sections[0].disagreements[0].sideA.marker, null, 'a side without a reference has no marker'); assert.equal(bare.sections[0].disagreements[0].sideB.quote, null)
})

test('references: the evidence level is a hint when it is not full text, urls are safe, missing fields show as nothing', () => {
  assert.equal(evidenceHint('full_text'), null); assert.equal(evidenceHint(null), null); assert.equal(evidenceHint('abstract'), 'abstract only'); assert.equal(evidenceHint('web_snippet'), 'web snippet'); assert.equal(evidenceHint('odd_level'), 'odd level')
  const refs = reportModel(demoWrittenResponse('completed')).references
  assert.deepEqual(refs.filter(r => r.hint).map(r => [r.number, r.hint]), [[3, 'abstract only'], [4, 'web snippet'], [6, 'web snippet']])
  assert.equal(refs[4].url, null, 'a reference without a url'); assert.ok(refs[0].url && refs[0].doi)
  assert.equal(safeUrl('javascript:alert(1)'), null); assert.equal(safeUrl('https://example.org/x'), 'https://example.org/x'); assert.equal(safeUrl(undefined), null)
  const odd = reportModel({ status: 'completed', report: { references: [{ number: 1 }, { number: 2, title: 'T', authors: ['A'], year: 2020 }, { title: 'no number' } as never] } })
  assert.deepEqual(odd.references.map(r => r.text), ['Reference 1', 'A (2020) T'])
})

test('unknown and missing fields show as nothing, never as an error', () => {
  const m = reportModel({ status: 'completed', report: { future: 1, overview: { summary: [{ text: 'A sentence.', tier: 'supported', newField: 1 } as never, { nope: 1 } as never], counts: { sections: 'many' as never, claims: 3 } }, sections: [{ title: 'S', sentences: [{ text: 'No refs here.', tier: 'single' }] }, {} as never] } } as never)
  assert.equal(m.summary.length, 1); assert.equal(m.summary[0].links.length, 0); assert.deepEqual(m.counts.map(c => c.key), ['claims'])
  assert.equal(m.sections.length, 2); assert.equal(m.sections[1].title, 'Section 2'); assert.deepEqual(m.limitations, [])
  assert.doesNotThrow(() => reportModel({ status: undefined as never, report: undefined as never })); assert.equal(reportModel({ status: 'x', report: null as never }).empty, true)
  assert.equal(reportModel({ status: 'completed', report: { sections: [{ title: 'T', sentences: [{ text: 'A.', tier: 'supported', refs: [7] }] }] } }).sections[0].sentences[0].links[0].found, false, 'a marker without a reference is plain text, not a link')
})

// ------------------------------------------------------------------------------------------------------------------------ 202, 404, generate
test('202 means "being written", 404 means "none", and the report appears when it is ready', async () => {
  assert.deepEqual((await demoApi.writtenReport('demo-completed')).state, 'none')
  assert.equal((await demoApi.writtenReport('no-such-run')).state, 'none')
  const seen: string[] = []
  for (let i = 0; i < 5; i++) seen.push((await demoApi.writtenReport('demo-written-running')).state)
  assert.deepEqual(seen.slice(0, 3), ['running', 'running', 'running']); assert.equal(seen[3], 'ready')
  const ok = await demoApi.writtenReport('demo-written-ok')
  assert.equal(ok.state, 'ready'); if (ok.state === 'ready') { assert.equal(ok.data.status, 'completed'); assert.ok(ok.data.markdown.startsWith('# ')); assert.match(ok.data.markdown, /^> How to read the findings/m) }
  for (const [id, status] of [['demo-factcheck', 'completed_with_warnings'], ['demo-written-insufficient', 'insufficient_evidence'], ['demo-written-failed', 'failed']] as const) {
    const r = await demoApi.writtenReport(id); assert.equal(r.state === 'ready' && r.data.status, status, id)
  }
})

test('Generate report: 400 when Stage 5 is off, 202 then polling until ready, 409 while it is running', async () => {
  await assert.rejects(demoApi.writeWrittenReport('demo-completed'), (e: { status?: number; message: string }) => e.status === 400 && /switched off/.test(e.message))
  assert.equal((await demoApi.writtenReport('demo-factcheck-old')).state, 'none')
  assert.deepEqual(await demoApi.writeWrittenReport('demo-factcheck-old'), { state: 'started' })
  await assert.rejects(demoApi.writeWrittenReport('demo-factcheck-old'), (e: { status?: number }) => e.status === 409)
  assert.equal((await demoApi.writtenReport('demo-factcheck-old')).state, 'running')
  assert.equal((await demoApi.writtenReport('demo-factcheck-old')).state, 'ready')
  await assert.rejects(demoApi.writeWrittenReport('no-such-run'), (e: { status?: number }) => e.status === 404)
  assert.equal(generateMessage(202, undefined).kind, 'started'); assert.equal(generateMessage(400, 'STAGE5 is off').text, 'STAGE5 is off'); assert.equal(generateMessage(400, undefined).kind, 'off')
  assert.equal(generateMessage(409, 'A write is already running for this id').kind, 'running'); assert.equal(generateMessage(409, 'the run has not finished').kind, 'error'); assert.equal(generateMessage(503, undefined).kind, 'error')
})

test('the Markdown file name is safe and the button of the run page follows the report stage', () => {
  assert.equal(downloadName('demo-written-ok'), 'trace-written-report-demo-written.md'); assert.equal(downloadName('../../x y'), 'trace-written-report-xy.md'); assert.equal(downloadName('///'), 'trace-written-report-run.md')
  assert.deepEqual(['completed', 'running', 'failed', 'pending', 'not_run', 'not_built', undefined].map(s => writtenReportButton(s as never)), ['open', 'writing', 'failed', null, null, null, null])
})

// ------------------------------------------------------------------------------------------------------------------------ the report stage
test('the report stage: states, labels, and no "not built yet" anywhere', async () => {
  assert.equal(stageMeta.report.name, 'Written report'); assert.ok(!/will write|not built/i.test(stageMeta.report.detail))
  assert.equal(stageStateWord('report', 'not_run'), 'not run'); assert.equal(stageStateWord('factcheck', 'not_run'), stageStateLabel.not_run)
  assert.equal(REPORT_NOT_RUN, 'not run (Stage 5 is switched off or Stage 4 did not run)')
  for (const v of Object.values(stageStateLabel)) assert.ok(!/not built/i.test(v), v)
  const stage = async (id: string) => (await demoApi.get(id)).stages.report
  assert.equal(await stage('demo-written-ok'), 'completed'); assert.equal(await stage('demo-factcheck'), 'completed'); assert.equal(await stage('demo-written-insufficient'), 'completed')
  assert.equal(await stage('demo-written-failed'), 'failed'); assert.equal(await stage('demo-completed'), 'not_run'); assert.equal(await stage('demo-factcheck-old'), 'not_run')
  assert.equal(await stage('demo-factcheck-failed'), 'not_run', 'Stage 4 failed: Stage 5 skipped itself')
  assert.equal((await demoApi.get('demo-written-failed')).status, 'completed', 'a Stage 5 failure never fails the run')
})

test('the report lane of the timeline: its steps, its notes, and no lane for a stage that did not run', () => {
  const warn = demoEvents({ fact: 'on' })
  const lane = reportLane(warn)!
  assert.deepEqual(lane.steps.map(s => s.id), ['sections', 'write', 'validate', 'summary', 'references', 'store']); assert.equal(lane.status, 'completed')
  assert.ok(lane.steps.every(s => s.status === 'completed')); assert.match(lane.summary, /sentences · 6 references · completed with warnings/)
  assert.ok(lane.steps.find(s => s.id === 'validate')!.chips.includes('1 dropped')); assert.equal(buildTimeline(warn, null).report!.id, 'report')
  const notes = notesOf(warn).filter(n => n.stage === 'report')
  assert.deepEqual(notes.map(n => [n.code, n.level]), [['stage5_fallback', 'warn'], ['stage5_dropped', 'warn']])
  assert.equal(noteView(notes[0]).title, '1 sentence uses the standard template wording'); assert.equal(noteView(notes[1]).title, '1 sentence was dropped by the final check')
  assert.equal(noteView({ ...notes[0], data: { count: 3 } }).title, '3 sentences use the standard template wording')
  // Stage 4 failed: the report stage skips itself with a note and has no lane
  const skipped = demoEvents({ fact: 'failed' })
  assert.equal(reportLane(skipped), null); assert.deepEqual(notesOf(skipped).filter(n => n.stage === 'report').map(n => n.code), ['stage5_skipped'])
  assert.match(noteView(notesOf(skipped).find(n => n.code === 'stage5_skipped')!).title, /skipped/)
  // Stage 5 off, and an old-style run: no report events at all
  assert.equal(reportLane(demoEvents({ fact: 'off' })), null); assert.equal(reportLane(demoEvents({ fact: 'on', old: true })), null)
  // a failed report stage fails only itself
  const failed = demoEvents({ fact: 'on', written: 'failed' })
  assert.equal(reportLane(failed)!.status, 'failed'); assert.ok(failed.some(e => e.event === 'run_completed') && !failed.some(e => e.event === 'run_failed'))
  assert.equal(reportLane(demoEvents({ fact: 'on', written: 'insufficient' }))!.status, 'completed')
})

// ------------------------------------------------------------------------------------------------------------------------ the answer (template s5-v2)
test('a note sentence (tier "note", template, no refs) has no tier label and no "plain wording" hint; a template sentence of another tier keeps its hint', () => {
  const t = tierView('note'); assert.equal(t.kind, 'note'); assert.equal(t.label, null)
  const m = reportModel({ status: 'completed', report: { overview: { summary: [
    { text: 'The evidence collected does not settle: X.', tier: 'note', origin: 'template', refs: [] },
    { text: 'One study reports Y.', tier: 'single', origin: 'template', refs: [1] },
  ] }, references: [{ number: 1, title: 'R' }] } })
  assert.equal(m.summary[0].tier.label, null); assert.equal(m.summary[0].plainWording, false); assert.deepEqual(m.summary[0].links, []); assert.equal(m.summary[0].markers, '')
  assert.equal(m.summary[1].tier.label, SINGLE_LABEL); assert.equal(m.summary[1].plainWording, true)
})

test('the demo report has an Answer with a note, and the Markdown says "Answer and Overview"; a report may have an empty conclusion', () => {
  const ok = demoWrittenResponse('completed'), warn = demoWrittenResponse('warnings')
  assert.ok((ok.report.overview?.summary ?? []).some(s => s.tier === 'note')); assert.match(ok.markdown, /## Answer and Overview/); assert.doesNotMatch(ok.markdown, /Executive Summary/)
  assert.equal(reportModel(ok).conclusion.length, 1); assert.deepEqual(warn.report.conclusion, []); assert.equal(reportModel(warn).conclusion.length, 0)
  assert.doesNotMatch(warn.markdown, /## Conclusion/)
})

// ------------------------------------------------------------------------------------------------------------------------ wording style s5-v3
test('s5-v3: the strength is shown only by the label and the markers; the legend is right for plain claims and for the older wording', () => {
  assert.equal(LEGEND, 'How to read the findings: a sentence without a label is stated by two or more documents; a finding marked (partly supported) rests on one document with a close variant in another; a finding marked (one source, not confirmed) is stated by a single document and says what that source is. Citation numbers point to the references at the end.')
  for (const [version, starts] of [['s5-v3', false], ['s5-v2', true]] as const) {
    const res = demoWrittenResponse('completed', undefined, version)
    assert.equal(res.templateVersion, version)
    const all = sentencesOf(res).filter(s => s.tier !== 'note')
    assert.equal(all.some(s => /^(Two sources|One source|One study) report/.test(s.text)), starts, `${version}: old opener`)
    const m = reportModel(res)
    assert.equal(m.legend, LEGEND, 'the same legend for both')
    // every partly / single sentence carries its label, in the Answer, the sections and the Conclusion alike
    for (const [where, views] of [['answer', m.summary], ['sections', m.sections.flatMap(x => x.sentences)], ['conclusion', m.conclusion]] as const) {
      for (const v of views) {
        if (v.tier.kind === 'partly') assert.equal(v.tier.label, 'partly supported', `${version} ${where}`)
        if (v.tier.kind === 'single') assert.equal(v.tier.label, 'one source, not confirmed', `${version} ${where}`)
      }
    }
    assert.ok(m.summary.some(v => v.tier.kind === 'single'), 'the answer has a single sentence with its label')
    assert.ok(m.conclusion.some(v => v.tier.kind === 'partly'), 'the conclusion has a partly sentence with its label')
    assert.equal((res.markdown.match(/\*\(one source, not confirmed\)\*/g) ?? []).length, all.filter(s => s.tier === 'single').length)
  }
})

// ------------------------------------------------------------------------------------------------------------------------ citations: the markers open the paper (docs/STAGE5_OUTPUT.md, "Added when the report is read")
const RUN = 'demo-written-ok'
const allViews = (m: ReturnType<typeof reportModel>): SentenceView[] => [
  ...m.summary, ...m.sections.flatMap(x => x.sentences), ...m.conclusion,
  ...(m.answer ? [...(m.answer.headline ? [m.answer.headline.view] : []), ...m.answer.parts.flatMap(p => [...(p.sentence ? [p.sentence] : []), ...p.supporting]), ...m.answer.others.map(o => o.view), ...m.answer.notes.map(o => o.view)] : []),
]

test('a marker is built from the citations: the paper at its quote, a not parsed paper, a web source, and the anchor as the fallback', () => {
  const m = reportModel(demoWrittenResponse('completed'), RUN)
  const [supported, partly, single] = m.sections[0].sentences
  const parsed = supported.links[0], notParsed = supported.links[1]
  assert.equal(parsed.kind, 'paper'); assert.equal(parsed.external, false)
  assert.equal(parsed.href, `/research/${RUN}/papers/demo-paper-1?finding=f_1a2b3c4d5e&from=written-report`, 'the paper page, at the finding of the first quote')
  assert.match(parsed.tooltip!, /\[Sample\] A Fictional Method for Signal Tracing\. Open the parsed paper$/)
  assert.equal(parsed.label, 'Reference 1: [Sample] A Fictional Method for Signal Tracing, open the parsed paper')
  assert.equal(notParsed.kind, 'paper'); assert.match(notParsed.tooltip!, /Open the paper \(not parsed: abstract and findings only\)$/); assert.match(notParsed.label, /not parsed/)
  assert.equal(notParsed.href, `/research/${RUN}/papers/demo-paper-2?finding=f_5e6f708192&from=written-report`)
  // a reference with no paper page and no url: the old anchor
  assert.equal(partly.links[1].kind, 'anchor'); assert.equal(partly.links[1].href, '#ref-5')
  // a web source: its url, in a new tab
  const web = m.sections[3].sentences[0].links[0]
  assert.deepEqual([web.n, web.kind, web.external, web.href], [6, 'web', true, 'https://example.org/sample-notebook']); assert.match(web.tooltip!, /Open the web page \(no parsed copy\)$/); assert.match(web.label, /opens in a new tab/)
  assert.equal(single.links[0].kind, 'paper')
  // no run id: no paper link (the anchor), a web source still opens its url
  const bare = reportModel(demoWrittenResponse('completed'))
  assert.equal(bare.sections[0].sentences[0].links[0].kind, 'anchor'); assert.equal(bare.sections[3].sentences[0].links[0].kind, 'web')
  // an old report has no citations at all: every marker is the anchor, exactly as before
  const old = reportModel(demoWrittenResponse('completed', undefined, 's5-v2'), RUN)
  assert.ok(allViews(old).every(v => v.links.every(l => l.kind === 'anchor' && l.href === `#ref-${l.n}`)) && allViews(old).every(v => v.evidenceCount === 0))
  assert.equal(old.answer, null); assert.ok(old.references.every(r => r.paper === null && r.citedIn === null))
})

test('markers: the run and paper ids are encoded, a url that is not http(s) is never linked, a missing reference or finding id degrades quietly', () => {
  assert.equal(paperHref('a/b c', 'p?1', 'f&1'), '/research/a%2Fb%20c/papers/p%3F1?finding=f%261&from=written-report'); assert.equal(paperHref('r', 'p'), '/research/r/papers/p?from=written-report')
  const refs = [{ number: 1, title: 'T', url: 'javascript:alert(1)' }, { number: 2, title: 'U', url: 'https://example.org/u' }]
  const web = { ref: 1, paperId: null, parsed: false, quotes: [] }
  assert.equal(markerFor(1, refs, [web], 'r').kind, 'anchor', 'javascript: is not a link')
  assert.equal(markerFor(2, refs, [{ ...web, ref: 2 }], 'r').kind, 'web')
  assert.equal(markerFor(2, refs, [{ ref: 2, paperId: 'p', parsed: true, quotes: [] }], 'r').href, '/research/r/papers/p?from=written-report', 'no quote: no finding parameter')
  assert.equal(markerFor(7, refs, [{ ...web, ref: 7 }], 'r').kind, 'plain'); assert.equal(markerFor(1, refs, undefined, 'r').kind, 'anchor')
})

test('Evidence (n): the verbatim quotes per reference, the relation in words, the hint for a source read in part, and the action of each quote', () => {
  const m = reportModel(demoWrittenResponse('completed'), RUN)
  const partly = m.sections[0].sentences[1]
  assert.equal(partly.evidenceCount, 2); assert.deepEqual(partly.evidence.map(e => e.ref), [1, 5])
  const [near, far] = [partly.evidence[0].quotes[0], partly.evidence[1].quotes[0]]
  assert.equal(near.relationLabel, 'supports'); assert.equal(far.relationLabel, 'close variant (another document)')
  assert.equal(near.text, 'On datasets below one thousand examples the advantage was not significant.')
  assert.deepEqual(near.open, { href: `/research/${RUN}/papers/demo-paper-1?finding=f_3c4d5e6f70&from=written-report`, label: 'Open in the paper', external: false })
  assert.equal(far.open, null, 'no paper page and no url: nowhere to go')
  const headline = m.sections[1].sentences[1]   // single, from an abstract
  assert.equal(headline.evidence[0].quotes[0].hint, 'abstract only'); assert.equal(headline.evidence[0].hint, 'abstract only')
  const web = m.sections[3].sentences[1].evidence[0].quotes[0]
  assert.equal(web.hint, 'web snippet'); assert.deepEqual([web.open?.label, web.open?.external, web.open?.href], ['Open the web page', true, 'https://example.org/sample-notebook'])
  // a note and a sentence without citations have no bar
  const note = reportModel({ status: 'completed', report: { overview: { summary: [{ text: 'The evidence collected does not settle: X.', tier: 'note', origin: 'template', refs: [], citations: [{ ref: 1, paperId: 'p', parsed: true, quotes: [{ text: 'q', findingId: 'f', paperId: 'p', parsed: true, relation: 'supports', evidenceLevel: null }] }] }, { text: 'Plain.', tier: 'supported', refs: [] }] }, references: [{ number: 1, title: 'R' }] } }, RUN)
  assert.deepEqual(note.summary.map(v => v.evidenceCount), [0, 0], 'a note never has evidence, whatever the server sent')
  // quotes without text are dropped, an unknown relation shows in words
  const odd = reportModel({ status: 'completed', report: { sections: [{ title: 'S', sentences: [{ text: 'A.', tier: 'supported', refs: [1], citations: [{ ref: 1, paperId: 'p', parsed: true, quotes: [{ text: ' ', findingId: 'f', paperId: 'p', parsed: true, relation: 'supports', evidenceLevel: null }, { text: 'kept', findingId: 'g', paperId: null, parsed: true, relation: 'odd_kind', evidenceLevel: 'full_text' }] }] }] }], references: [{ number: 1, title: 'R' }] } }, RUN)
  const q = odd.sections[0].sentences[0].evidence[0].quotes
  assert.equal(q.length, 1); assert.equal(q[0].relationLabel, 'odd kind'); assert.match(q[0].open!.href, /papers\/p\?finding=g/, 'the paper of the citation stands in for a quote without its own')
})

test('every citation of the demo reports points at a finding that exists on the demo paper, with the same text (except the one that shows the "finding not found" state)', async () => {
  const res = demoWrittenResponse('completed')
  const cites = [...(res.report.overview?.summary ?? []), ...(res.report.sections ?? []).flatMap(s => s.sentences ?? []), ...(res.report.conclusion ?? [])].flatMap(s => s.citations ?? [])
  assert.ok(cites.length > 0)
  const refs = res.report.references ?? []
  for (const c of cites) {
    assert.equal(c.paperId, refs.find(r => r.number === c.ref)?.paper?.id ?? null, `the citation of reference ${c.ref} and the reference agree on the paper`)
    for (const q of c.quotes) {
      if (!c.paperId || c.paperId === 'demo-paper-4') continue
      const f = demoDetail(c.paperId, 'evidence')!.findings.find(x => x.id === q.findingId)
      assert.ok(f, `finding ${q.findingId} is on ${c.paperId}`); assert.equal(f!.quote, q.text)
    }
  }
  const d = await demoApi.paper(RUN, 'demo-paper-1')
  assert.ok(d.findings.every(f => /^f_[0-9a-f]{10}$/.test(f.id ?? '')) && new Set(d.findings.map(f => f.id)).size === d.findings.length, 'the demo findings have unique ids like the server')
  assert.equal(d.findings.find(f => f.id === 'f_4d5e6f7081')!.spans.length, 0, 'a quote that could not be located has no spans')
  const n = await demoApi.paper(RUN, 'demo-paper-2'); assert.equal(n.parsed, null); assert.ok(n.findings.some(f => f.id === 'f_5e6f708192'), 'a paper that was not parsed still has its findings')
})

test('references: the actions to open the paper, and in how many sentences each is cited', () => {
  const refs = reportModel(demoWrittenResponse('completed'), RUN).references
  assert.deepEqual(refs[0].paper, { href: `/research/${RUN}/papers/demo-paper-1?from=written-report`, parsed: true, label: 'Open parsed paper' })
  assert.deepEqual([refs[1].paper?.parsed, refs[1].paper?.label], [false, 'Open paper page (not parsed)'])
  assert.deepEqual(refs.map(r => r.paper === null), [false, false, false, true, true, true], 'a web page has only "Open source"'); assert.ok(refs[3].url && refs[5].url)
  assert.ok(refs.every(r => typeof r.citedIn === 'number')); assert.equal(refs[0].citedIn, 4, 'the answer, two sentences of section 1, and the conclusion')
  assert.ok(reportModel(demoWrittenResponse('completed')).references.every(r => r.paper === null), 'without a run id there is no paper link')
})

// ------------------------------------------------------------------------------------------------------------------------ collapse bars
test('the bar of a section says what is in it, in words that do not claim more than the data, and keeps the hints visible', () => {
  const m = reportModel(demoWrittenResponse('completed'), RUN)
  assert.deepEqual(m.sections.map(s => s.summary), [
    '3 findings · 1 supported · 1 partly supported · 1 one source, not confirmed · 1 disagreement · 1 left out (filtered)',
    '2 findings · 1 supported · 1 one source, not confirmed · 1 left out (filtered)',
    'no findings written',
    '2 findings · 1 partly supported · 1 one source, not confirmed',
  ])
  assert.deepEqual(m.sections.map(s => s.hints), [['sources disagree'], ['evidence gaps'], ['evidence gaps'], []])
  assert.equal(sectionSummary([{ tier: tierView('supported') }], 0), '1 finding · 1 supported')
  assert.equal(sectionSummary([{ tier: tierView('mystery') }], 2, { filtered: 0 }), '1 finding · 1 not confirmed (kind unknown) · 2 disagreements')
  assert.equal(sectionSummary([], 1), '0 findings · 1 disagreement', 'a section with only a disagreement still says so')
  for (const s of m.sections) assert.ok(!/\b(reliable|verified|proven|confirmed)\b/.test(s.summary.replace(/not confirmed/g, '')), s.summary)
})

// ------------------------------------------------------------------------------------------------------------------------ the Answer (overview.answer)
test('the answer view: the headline, the parts, the strength line as the server wrote it, the figures, and what is open', () => {
  const res = demoWrittenResponse('completed')
  const a = reportModel(res, RUN).answer!
  assert.ok(a)
  assert.deepEqual([a.headline!.index, a.headline!.id, a.headline!.view.tier.kind, a.headline!.view.tier.label], [0, 'wr-sum-0', 'supported', null])
  assert.deepEqual(a.parts.map(p => [p.index, p.isHeadline, p.sectionId]), [[0, true, 'sec-1'], [1, false, 'sec-2']])
  assert.equal(a.parts[0].sentence, null, 'the part that is the headline is not written twice'); assert.equal(a.parts[1].sentence!.tier.label, SINGLE_LABEL)
  assert.deepEqual(a.parts[0].supporting.map(v => v.tier.label), [PARTLY_LABEL, SINGLE_LABEL]); assert.ok(a.parts[0].supporting.every(v => v.links.length > 0))
  const st = a.strength!, raw = res.report.overview!.answer!.strength
  assert.equal(st.line, raw.line, 'the line is shown as the server wrote it'); assert.equal(st.total, raw.statements); assert.equal(st.tiers.reduce((t, x) => t + x.value, 0), st.total)
  assert.ok(Math.abs(st.tiers.reduce((t, x) => t + x.pct, 0) - 100) < 1e-9); assert.match(st.barLabel, /partly supported/); assert.match(st.barLabel, /one source, not confirmed/)
  assert.deepEqual(a.figures.map(f => [f.value, f.anchor, f.tierLabel, f.tierKind]), [['10%', 'wr-sum-1', SINGLE_LABEL, 'single']], 'a figure from a single source carries that label')
  assert.equal(a.openQuestions.length, 2); assert.deepEqual(a.notes, [], 'the template note is not shown twice when the open questions are listed'); assert.deepEqual(a.others, [])
  assert.deepEqual([a.disputes.count, a.disputes.items[0].anchor, a.disputes.items[0].refs.map(r => r.n)], [1, 'wr-dis-sec-1-0', [4, 5]])
  assert.ok(!/\b(false|wrong|incorrect|untrue)\b/i.test(JSON.stringify(a.disputes.items.map(d => [d.claimA, d.claimB]))), 'a dispute never says that one side is false')
})

test('the answer view without overview.answer, with a broken one, and with sentences it does not place: nothing of overview.summary is lost', () => {
  const res = demoWrittenResponse('completed')
  const without = structuredClone(res); delete without.report.overview!.answer
  const m = reportModel(without, RUN)
  assert.equal(m.answer, null); assert.equal(m.summary.length, 3, 'the page falls back to today\'s rendering of overview.summary'); assert.equal(m.summary[1].tier.label, SINGLE_LABEL)
  assert.equal(reportModel(demoWrittenResponse('completed', undefined, 's5-v2'), RUN).answer, null)
  assert.equal(reportModel(demoWrittenResponse('insufficient'), RUN).answer, null); assert.equal(reportModel(demoWrittenResponse('failed'), RUN).answer, null)
  // an answer with nothing placed: every sentence of the summary shows up in `others`, the template note shows when there are no open questions
  const bare = structuredClone(res); bare.report.overview!.answer = { headline: null, parts: [], strength: undefined as never, figures: [], openQuestions: [], disputes: { count: 0, items: [] } }
  const a = reportModel(bare, RUN).answer!
  assert.deepEqual(a.others.map(o => o.index), [0, 1]); assert.deepEqual(a.notes.map(o => o.index), [2]); assert.equal(a.strength, null); assert.equal(a.headline, null)
  assert.equal(a.others[1].view.tier.label, SINGLE_LABEL)
  // indexes that point nowhere are ignored, never an error
  const wild = structuredClone(res); wild.report.overview!.answer!.headline = { sentenceIndex: 99 }; wild.report.overview!.answer!.parts = [{ sentenceIndex: -1, sectionId: null, title: null, sentence: { text: 'x', tier: 'single' }, supporting: [] }]
  wild.report.overview!.answer!.figures = [{ value: '7%', sentenceIndex: 50, refs: [] }, { value: '', sentenceIndex: 0, refs: [] }]
  const w = reportModel(wild, RUN).answer!
  assert.equal(w.headline, null); assert.equal(w.parts.length, 0); assert.deepEqual(w.figures.map(f => [f.value, f.anchor, f.tierLabel]), [['7%', null, null]]); assert.deepEqual(w.others.map(o => o.index), [0, 1])
  assert.doesNotThrow(() => reportModel({ status: 'completed', report: { overview: { summary: [], answer: 'x' as never } } }, RUN)); assert.equal(reportModel({ status: 'completed', report: { overview: { summary: [], answer: 'x' as never } } }, RUN).answer, null)
})

test('every tier-label rule holds in the new places: the headline, the parts, the supporting sentences, the others, the figures and the evidence', () => {
  for (const kind of ['completed', 'warnings'] as const) {
    const m = reportModel(demoWrittenResponse(kind), RUN)
    const views = allViews(m)
    assert.ok(views.length > 8)
    for (const v of views) {
      if (v.tier.kind === 'partly') assert.equal(v.tier.label, 'partly supported')
      if (v.tier.kind === 'single') assert.equal(v.tier.label, 'one source, not confirmed')
      if (v.tier.kind === 'note') assert.deepEqual([v.tier.label, v.links.length, v.evidenceCount, v.plainWording], [null, 0, 0, false], 'a note has no label, no markers, no evidence bar')
      if (v.evidenceCount > 0 && v.tier.kind !== 'supported') assert.ok(v.tier.label, 'the bar of a sentence that is not a confirmed one repeats its label')
    }
    const a = m.answer!
    assert.ok(a.parts.flatMap(p => p.supporting).some(v => v.tier.kind === 'partly') && a.parts.flatMap(p => p.supporting).some(v => v.tier.kind === 'single'))
    for (const f of a.figures) assert.ok(f.tierKind === 'supported' || f.tierLabel, 'a figure from a sentence that is not confirmed is labelled')
  }
})
