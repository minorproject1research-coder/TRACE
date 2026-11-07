'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { ArrowRight, Check, Search } from 'lucide-react'
import { PaperCard, WebCard } from '@/components/trace/paper-card'
import { Timeline } from '@/components/trace/timeline'
import { EmptyState, ErrorState, Skeleton } from '@/components/trace/states'
import { TabFixed, TabScroll } from '@/components/trace/tab-layout'
import { num } from '@/lib/format'
import { radioGroupKeys } from '@/lib/radio-keys'
import type { PapersOverview, PaperSummary, StageState, StreamStatus, WorkflowEvent } from '@/lib/trace-types'
import type { Async } from '@/lib/use-research'

type View = 'timeline' | 'plan' | 'papers' | 'web'
type PaperFilter = 'all' | 'parsed' | 'used' | 'not_parsed' | 'pdf'
type Sort = 'match' | 'year' | 'citations'

const PAGE = 20
const VIEW_LABEL: Record<View, string> = { timeline: 'Timeline', plan: 'Plan', papers: 'Papers', web: 'Web sources' }

function Step({ value, label, hint, onClick, active, pending }: { value: number | null; label: string; hint: string; onClick?: () => void; active?: boolean; pending?: boolean }) {
  const body = <><strong>{value ?? '–'}</strong><span>{label}</span><small className="sr-only">{hint}</small></>
  return onClick
    ? <button type="button" title={hint} className={`funnel-step ${active ? 'on' : ''} ${pending ? 'pending' : ''}`} onClick={onClick} aria-pressed={active}>{body}</button>
    : <div title={hint} className={`funnel-step static ${pending ? 'pending' : ''}`}>{body}</div>
}

export function ActivityTab(props: {
  runId: string; events: WorkflowEvent[]; streamStatus: StreamStatus; streamDetail?: string; running: boolean; papers: Async<PapersOverview>; mode: 'live' | 'demo'; factcheckState?: StageState
}) {
  const { runId, events, streamStatus, streamDetail, running, papers, mode, factcheckState } = props
  const ov = papers.data
  const [view, setView] = useState<View>('timeline')
  const [filter, setFilter] = useState<PaperFilter>('all')
  const [query, setQuery] = useState('')
  const [subQ, setSubQ] = useState('')
  const [sort, setSort] = useState<Sort>('match')
  const [shown, setShown] = useState(PAGE)
  const touched = useRef(false)
  const scroller = useRef<HTMLDivElement>(null)

  const pick = (v: View, f?: PaperFilter) => { touched.current = true; setView(v); if (f) { setFilter(f); setShown(PAGE) } }

  // Opening a run that has already finished lands on its papers; a run that is still going stays on the Timeline (it is the live view).
  const decided = useRef(false)
  useEffect(() => {
    if (decided.current || !ov) return
    decided.current = true
    if (!touched.current && !running && ov.counts.papersKept > 0) setView('papers')
  }, [ov, running])

  // A new view or filter starts at the top of its list.
  useEffect(() => { scroller.current?.scrollTo({ top: 0 }) }, [view, filter, subQ, sort, query])

  // What the events already say, before (or without) the database list.
  const paperEv = num(events.find(e => e.event === 'branch_completed' && e.data.branch === 'papers')?.data, 'papers')
    ?? num(events.find(e => e.event === 'step' && e.data.lane === 'papers' && e.data.step === 'store' && e.data.state === 'completed')?.data, 'stored')
  const webEv = num(events.find(e => e.event === 'branch_completed' && e.data.branch === 'web')?.data, 'webSources')
    ?? num(events.find(e => e.event === 'step' && e.data.lane === 'web' && e.data.step === 'search' && e.data.state === 'completed')?.data, 'found')
  const c = ov?.counts
  const kept = c?.papersKept ?? paperEv
  const web = c?.webFound ?? webEv

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    const list = (ov?.papers ?? []).filter((p: PaperSummary) =>
      (filter === 'all' || (filter === 'parsed' && p.parse.status === 'parsed') || (filter === 'not_parsed' && p.parse.status !== 'parsed') || (filter === 'used' && !!p.evidence) || (filter === 'pdf' && !!p.pdfUrl)) &&
      (!subQ || p.subQuestionId === subQ) &&
      (!q || (p.title ?? '').toLowerCase().includes(q) || p.authors.some(a => a.toLowerCase().includes(q)) || (p.venue ?? '').toLowerCase().includes(q)))
    const by = { match: (p: PaperSummary) => p.scores.combined ?? 0, year: (p: PaperSummary) => p.year ?? 0, citations: (p: PaperSummary) => p.citations ?? 0 }[sort]
    return [...list].sort((a, b) => by(b) - by(a))
  }, [ov, filter, query, subQ, sort])

  const perQuestion = useMemo(() => (ov?.subQuestions ?? []).map(q => {
    const ps = ov!.papers.filter(p => p.subQuestionId === q.id)
    const ws = ov!.web.filter(w => w.subQuestionId === q.id)
    return { ...q, kept: ps.length, parsed: ps.filter(p => p.parse.status === 'parsed').length, used: ps.filter(p => p.evidence).length, web: ws.length, webUsed: ws.filter(w => w.evidence).length }
  }), [ov])

  const planner = events.find(e => e.stage === 'planner' && e.event === 'stage_completed')
  const topics = (planner?.data.topics as string[] | undefined) ?? []

  const loadingNote = ov === null && papers.loading ? <Skeleton rows={3} label="Loading papers" /> : null
  const hasPapers = !papers.error && !!ov && ov.papers.length > 0

  return (
    <>
      <TabFixed>
        <section className="funnel" aria-label="Evidence funnel">
          <div className="funnel-row">
            <span className="funnel-label">Papers</span>
            <Step value={kept} label="kept" hint="after relevance filter" onClick={() => pick('papers', 'all')} active={view === 'papers' && filter === 'all'} pending={kept == null} />
            <ArrowRight size={16} className="funnel-arrow" aria-hidden="true" />
            <Step value={c?.papersParsed ?? null} label="parsed" hint="content extracted" onClick={() => pick('papers', 'parsed')} active={view === 'papers' && filter === 'parsed'} pending={!c} />
            <ArrowRight size={16} className="funnel-arrow" aria-hidden="true" />
            <Step value={c?.papersUsedAsEvidence ?? null} label="used as evidence" hint={c ? `${c.papersUsedFullText} full text · ${c.papersUsedAbstractOnly} abstract` : 'after judging'} onClick={() => pick('papers', 'used')} active={view === 'papers' && filter === 'used'} pending={!c || (running && !c.papersUsedAsEvidence)} />
          </div>
          <div className="funnel-row">
            <span className="funnel-label">Web</span>
            <Step value={web} label="sources found" hint="snippets only" onClick={() => pick('web')} active={view === 'web'} pending={web == null} />
            <ArrowRight size={16} className="funnel-arrow" aria-hidden="true" />
            <Step value={c?.webUsedAsEvidence ?? null} label="used as evidence" hint="after judging" onClick={() => pick('web')} pending={!c || (running && !c.webUsedAsEvidence)} />
          </div>
        </section>

        <div className="segmented activity-views" role="radiogroup" aria-label="Activity view" onKeyDown={radioGroupKeys}>
          {(Object.keys(VIEW_LABEL) as View[]).map(v => (
            <button key={v} type="button" role="radio" aria-checked={view === v} tabIndex={view === v ? 0 : -1} className={view === v ? 'gborder' : ''} onClick={() => pick(v)}>
              {VIEW_LABEL[v]}{v === 'papers' && kept != null ? <span className="count">{kept}</span> : null}{v === 'web' && web != null ? <span className="count">{web}</span> : null}
            </button>
          ))}
        </div>

        {view === 'papers' && hasPapers && (
          <>
            <div className="toolbar compact">
              <label className="search-field"><Search size={15} aria-hidden="true" /><span className="sr-only">Filter papers by title, author or venue</span>
                <input value={query} onChange={e => { setQuery(e.target.value); setShown(PAGE) }} placeholder="Filter by title, author or venue…" /></label>
              <label className="select-field"><span className="sr-only">Sub-question</span>
                <select value={subQ} onChange={e => { setSubQ(e.target.value); setShown(PAGE) }}><option value="">All sub-questions</option>{ov!.subQuestions.map(q => <option key={q.id} value={q.id}>{q.topic}</option>)}</select></label>
              <label className="select-field"><span className="sr-only">Sort by</span>
                <select value={sort} onChange={e => setSort(e.target.value as Sort)}><option value="match">Best match</option><option value="year">Newest</option><option value="citations">Most cited</option></select></label>
            </div>
            <div className="chips" role="group" aria-label="Paper filter">
              {([['all', 'All'], ['parsed', 'Parsed'], ['used', 'Used as evidence'], ['not_parsed', 'Not parsed'], ['pdf', 'Has PDF link']] as [PaperFilter, string][]).map(([k, l]) => (
                <button key={k} type="button" className={`chip ${filter === k ? 'on' : ''}`} aria-pressed={filter === k} onClick={() => { setFilter(k); setShown(PAGE) }}>{filter === k && <Check size={12} aria-hidden="true" />}{l}</button>))}
              <span className="meta" aria-live="polite">{filtered.length} of {ov!.papers.length} papers</span>
            </div>
          </>
        )}
      </TabFixed>

      <TabScroll label={`${VIEW_LABEL[view]} list`} scrollRef={scroller}>
          {view === 'timeline' && <Timeline events={events} overview={ov} streamStatus={streamStatus} streamDetail={streamDetail} running={running} factcheckState={factcheckState} />}

          {view === 'plan' && (
            <div className="view-body">
              <h2 className="sub-h">What TRACE planned</h2>
              {planner && <p className="meta">{num(planner.data, 'subQuestions') ?? topics.length} sub-questions · {num(planner.data, 'queries') ?? '?'} search queries{planner.data.domainAnchor ? <> · field: <b>{String(planner.data.domainAnchor)}</b></> : null}</p>}
              {perQuestion.length === 0 && topics.length === 0 && <p className="meta">{running ? 'The planner has not finished yet.' : 'No plan was recorded for this run.'}</p>}
              {perQuestion.length > 0
                ? <ol className="plan-list">{perQuestion.map(q => (
                    <li key={q.id}><b>{q.topic}</b>
                      <div className="source-tags">
                        <span className="tag">{q.kept} papers kept</span><span className="tag">{q.parsed} parsed</span><span className="tag">{q.used} used as evidence</span><span className="tag">{q.web} web ({q.webUsed} used)</span>
                        <button type="button" className="link-button" onClick={() => { setSubQ(q.id); pick('papers', 'all') }}>See its papers <ArrowRight size={13} aria-hidden="true" /></button>
                      </div></li>))}</ol>
                : topics.length > 0 && <ol className="plan-list">{topics.map(t => <li key={t}><b>{t}</b></li>)}</ol>}
            </div>
          )}

          {view === 'papers' && (
            <div className="view-body">
              <h2 className="sr-only">Papers kept</h2>
              {loadingNote}
              {papers.error && <ErrorState title="Could not load the papers" message={papers.error.message} status={papers.error.status} onRetry={papers.reload} />}
              {!papers.error && ov && ov.papers.length === 0 && <EmptyState title={running ? 'No papers yet' : 'No papers were kept'} message={running ? 'Papers appear here as soon as retrieval has filtered them.' : 'This run kept no papers.'} />}
              {hasPapers && (
                <>
                  {filtered.length === 0 ? <EmptyState title="No paper matches" message="Change or clear the filters." action={<button className="link-button" onClick={() => { setFilter('all'); setQuery(''); setSubQ('') }}>Clear filters</button>} />
                    : <div className="card-list">{filtered.slice(0, shown).map(p => <PaperCard key={p.id} paper={p} runId={runId} />)}</div>}
                  {filtered.length > shown && <button className="tool-button more" onClick={() => setShown(n => n + PAGE)}>Show {Math.min(PAGE, filtered.length - shown)} more</button>}
                  <p className="meta">The funnel starts at the papers kept: candidates removed by the relevance filter are not stored. {mode === 'live' ? 'Parsed means TRACE stored the paper’s extracted content. Open a paper to read it and see where each quote comes from.' : ''}</p>
                </>
              )}
            </div>
          )}

          {view === 'web' && (
            <div className="view-body">
              <h2 className="sr-only">Web sources</h2>
              {loadingNote}
              {papers.error && <ErrorState title="Could not load the web sources" message={papers.error.message} status={papers.error.status} onRetry={papers.reload} />}
              {!papers.error && ov && ov.web.length === 0 && <EmptyState title={running ? 'No web sources yet' : 'No web sources'} message="Web search results appear here once the web branch finishes." />}
              {!papers.error && ov && ov.web.length > 0 && <div className="card-list">{ov.web.slice(0, shown).map(w => <WebCard key={w.id} web={w} />)}</div>}
              {ov && ov.web.length > shown && <button className="tool-button more" onClick={() => setShown(n => n + PAGE)}>Show {Math.min(PAGE, ov.web.length - shown)} more</button>}
            </div>
          )}
      </TabScroll>
    </>
  )
}
