'use client'

import Link from 'next/link'
import { useParams } from 'next/navigation'
import { ArrowLeft, FileSearch, Hourglass, PenLine } from 'lucide-react'
import { ReportView } from '@/components/ReportView'
import { EmptyState, ErrorState, Skeleton } from '@/components/trace/states'
import { useWrittenReport } from '@/lib/use-research'
import { NONE_TEXT, NONE_TITLE, WRITING_TEXT, WRITING_TITLE } from '@/lib/written-report'

/** The written report (Stage 5) of a run. 202 = being written (it asks again every 3 seconds), 404 = none stored (with a button to write it), 503 = try again. */
export default function WrittenReportPage() {
  const { id: rawId } = useParams<{ id: string }>()
  const id = decodeURIComponent(rawId)
  const { state, message, generating, generate, reload } = useWrittenReport(id)
  const enc = encodeURIComponent(id)
  const back = <Link className="back-link" href={`/research/${enc}`}><ArrowLeft size={14} aria-hidden="true" /> Back to run</Link>
  const evidence = <Link className="link-button strong" href={`/research/${enc}/report`}><FileSearch size={14} aria-hidden="true" /> Open the evidence report</Link>

  if (state.phase === 'loading') return <>{back}<h1 className="sr-only">Written report</h1><Skeleton rows={6} label="Loading the written report" /></>
  if (state.phase === 'error') {
    return <>{back}<h1 className="sr-only">Written report</h1><ErrorState title={state.error.status === 503 ? 'The database is not available' : 'Could not load the written report'} message={state.error.status === 503 ? 'TRACE could not reach its database just now. Try again in a moment.' : state.error.message} status={state.error.status} onRetry={reload} /></>
  }
  if (state.phase === 'running') {
    return (
      <>
        {back}<h1 className="sr-only">Written report</h1>
        <div className="state-box" role="status" aria-live="polite"><Hourglass size={22} aria-hidden="true" /><div><b>{WRITING_TITLE}</b><p>{WRITING_TEXT}</p>{message && <p className="meta">{message.text}</p>}<p>{evidence}</p></div></div>
      </>
    )
  }
  if (state.phase === 'none') {
    return (
      <>
        {back}<h1 className="sr-only">Written report</h1>
        <EmptyState title={NONE_TITLE} message={NONE_TEXT} action={
          <div className="wr-none-actions">
            <button type="button" className="start-button" onClick={generate} disabled={generating}><PenLine size={15} aria-hidden="true" />{generating ? 'Starting…' : 'Generate report'}</button>
            {evidence}
            <p className="meta" role="status" aria-live="polite">{message?.text ?? ''}</p>
          </div>} />
      </>
    )
  }
  return <>{back}<ReportView runId={id} res={state.data} /></>
}
