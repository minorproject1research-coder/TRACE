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
import {
  downloadName, evidenceHint, generateMessage, LEGEND, markers, PARTLY_LABEL, refFor, reportModel, safeUrl, sentenceParts, SINGLE_LABEL, statusView, tierView, writtenReportButton,
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
    for (const v of [...m.summary, ...m.sections.flatMap(x => x.sentences), ...m.conclusion]) for (const l of v.links) { assert.equal(l.href, `#ref-${l.n}`); assert.ok(l.found, `reference ${l.n} exists`); assert.ok(m.references.some(r => r.anchor === `ref-${l.n}`)) }
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
    assert.equal(m.legend, LEGEND); assert.match(m.legend, /Two sources report/); assert.match(m.legend, /partly supported/); assert.match(m.legend, /not confirmed/)
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
  const text = JSON.stringify(d)
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
