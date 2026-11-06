'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useMode } from './mode'
import { ApiError, type PaperDetail, type PapersOverview, type Report, type RunSummary, type Session, type StreamStatus, type WorkflowEvent } from './trace-types'

export type Async<T> = { data: T | null; error: ApiError | null; loading: boolean; reload: () => void }

/** Runs `fn` on mount and whenever `key` changes. Stale results (a previous key, an unmounted page) are dropped. */
function useAsync<T>(fn: (() => Promise<T>) | null, key: string): Async<T> {
  const [state, setState] = useState<{ data: T | null; error: ApiError | null; loading: boolean }>({ data: null, error: null, loading: fn !== null })
  const [tick, setTick] = useState(0)
  const fnRef = useRef(fn)
  fnRef.current = fn
  useEffect(() => {
    const run = fnRef.current
    if (!run) { setState({ data: null, error: null, loading: false }); return }
    let cancelled = false
    setState(s => ({ ...s, loading: true, error: null }))
    run().then(
      data => { if (!cancelled) setState({ data, error: null, loading: false }) },
      (e: unknown) => { if (!cancelled) setState({ data: null, error: e instanceof ApiError ? e : new ApiError(e instanceof Error ? e.message : 'Something went wrong'), loading: false }) },
    )
    return () => { cancelled = true }
  }, [key, tick])
  return { ...state, reload: useCallback(() => setTick(t => t + 1), []) }
}

export function useRuns(limit = 20): Async<RunSummary[]> {
  const { api } = useMode()
  return useAsync(() => api.list(limit), `${api.mode}:runs:${limit}`)
}

export function useSession(id: string): Async<Session> & { refresh: () => void; setSession: (s: Session) => void } {
  const { api } = useMode()
  const result = useAsync(() => api.get(id), `${api.mode}:session:${id}`)
  const [override, setOverride] = useState<Session | null>(null)
  useEffect(() => setOverride(null), [id, api])
  // A background refresh keeps the screen up; only the first load shows a spinner.
  const refresh = useCallback(() => { api.get(id).then(setOverride, () => { /* keep what we have */ }) }, [api, id])
  return { ...result, data: override ?? result.data, refresh, setSession: setOverride }
}

export function useReport(id: string, enabled: boolean): Async<Report> {
  const { api } = useMode()
  // The API can answer 404 for a run that exists when its database read fails transiently, so a 404 is retried once.
  const load = () => api.report(id).catch(async (e: unknown) => {
    if (e instanceof ApiError && e.status === 404) { await new Promise(r => setTimeout(r, 900)); return api.report(id) }
    throw e
  })
  return useAsync(enabled ? load : null, `${api.mode}:report:${id}:${enabled}`)
}

/** Papers and web sources kept so far. `version` changes when the run progressed (a stage or branch finished): the list is read again. */
export function usePapers(id: string, enabled: boolean, version: number): Async<PapersOverview> {
  const { api } = useMode()
  return useAsync(enabled ? () => api.papers(id) : null, `${api.mode}:papers:${id}:${enabled}:${version}`)
}

export function usePaper(id: string, paperId: string): Async<PaperDetail> {
  const { api } = useMode()
  return useAsync(() => api.paper(id, paperId), `${api.mode}:paper:${id}:${paperId}`)
}

/** Follows the run's event stream. Events are de-duplicated by seq; the hook returns them in order. */
export function useRunStream(id: string, onAnyEvent?: (event: WorkflowEvent) => void): { events: WorkflowEvent[]; status: StreamStatus; detail?: string } {
  const { api } = useMode()
  const [events, setEvents] = useState<WorkflowEvent[]>([])
  const [status, setStatus] = useState<StreamStatus>('connecting')
  const [detail, setDetail] = useState<string>()
  const handlerRef = useRef(onAnyEvent)
  handlerRef.current = onAnyEvent
  useEffect(() => {
    setEvents([]); setStatus('connecting'); setDetail(undefined)
    return api.subscribe(id, {
      onEvent: ev => {
        setEvents(prev => (prev.some(p => p.seq === ev.seq) ? prev : [...prev, ev].sort((a, b) => a.seq - b.seq)))
        handlerRef.current?.(ev)
      },
      onStatus: (s, d) => { setStatus(s); setDetail(d) },
    })
  }, [api, id])
  return { events, status, detail }
}
