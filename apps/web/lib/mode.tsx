'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { demoApi } from './demo-api'
import { API_LABEL, liveApi } from './trace-api'
import type { TraceApi } from './trace-types'

export type Mode = 'live' | 'demo'
export type HealthState = { state: 'checking' | 'online' | 'offline'; activeRuns: number; error?: string }

/** Set NEXT_PUBLIC_TRACE_ENABLE_DEMO=false to remove demo mode (for example in production). */
export const DEMO_ENABLED = process.env.NEXT_PUBLIC_TRACE_ENABLE_DEMO !== 'false'

type Ctx = { ready: boolean; demoEnabled: boolean; mode: Mode; setMode: (m: Mode) => void; api: TraceApi; health: HealthState; refreshHealth: () => void; apiUrl: string }

const ModeContext = createContext<Ctx | null>(null)
const MODE_KEY = 'trace.mode'

export function ModeProvider({ children }: { children: React.ReactNode }) {
  // Live is the default and demo is always an explicit choice. Initial render is always 'live' so server and client markup agree.
  const [mode, setModeState] = useState<Mode>('live')
  const [ready, setReady] = useState(false)   // false until the saved mode is read: no request may go out before that
  const [health, setHealth] = useState<HealthState>({ state: 'checking', activeRuns: 0 })
  const [tick, setTick] = useState(0)

  useEffect(() => { try { if (DEMO_ENABLED && localStorage.getItem(MODE_KEY) === 'demo') setModeState('demo') } catch { /* storage blocked */ } setReady(true) }, [])

  const setMode = useCallback((m: Mode) => {
    if (m === 'demo' && !DEMO_ENABLED) return
    setModeState(m)
    setHealth({ state: 'checking', activeRuns: 0 })
    try { localStorage.setItem(MODE_KEY, m) } catch { /* storage blocked */ }
  }, [])

  const api = mode === 'demo' ? demoApi : liveApi

  useEffect(() => {
    if (!ready) return
    let cancelled = false
    const check = () => api.health().then(
      h => { if (!cancelled) setHealth({ state: 'online', activeRuns: h.activeRuns }) },
      (e: unknown) => { if (!cancelled) setHealth({ state: 'offline', activeRuns: 0, error: e instanceof Error ? e.message : 'unreachable' }) },
    )
    check()
    const timer = setInterval(check, 20_000)
    return () => { cancelled = true; clearInterval(timer) }
  }, [api, tick, ready])

  const value = useMemo<Ctx>(() => ({ ready, demoEnabled: DEMO_ENABLED, mode, setMode, api, health, refreshHealth: () => setTick(t => t + 1), apiUrl: API_LABEL }), [ready, mode, setMode, api, health])
  return <ModeContext.Provider value={value}>{children}</ModeContext.Provider>
}

export function useMode() {
  const ctx = useContext(ModeContext)
  if (!ctx) throw new Error('useMode must be used inside <ModeProvider>')
  return ctx
}
