'use client'

import { FlaskConical, Radio } from 'lucide-react'
import { StatusPill } from '@/components/trace/status-pill'
import { useMode, type Mode } from '@/lib/mode'
import { radioGroupKeys } from '@/lib/radio-keys'

const options: { value: Mode; title: string; icon: React.ReactNode; body: string }[] = [
  { value: 'live', title: 'Live', icon: <Radio size={20} />, body: 'Talks to the real TRACE FastAPI backend. A run takes 15 to 25 minutes and uses the model server and external APIs.' },
  { value: 'demo', title: 'Demo', icon: <FlaskConical size={20} />, body: 'A browser-side simulator with fictional sample data. Runs finish in about 13 seconds. Nothing reaches the backend or the database.' },
]

export default function SettingsPage() {
  const { demoEnabled, mode, setMode, health, refreshHealth, apiUrl } = useMode()
  return (
    <>
      <section className="page-head rise"><div><div className="eyebrow">Settings</div><h1>Connection and mode</h1><p>{demoEnabled ? 'Choose whether TRACE runs against the real backend or a clearly labelled demo.' : 'TRACE is connected to the real backend.'}</p></div></section>

      <section className="settings-grid rise" style={{ '--i': 1 } as React.CSSProperties} aria-labelledby="mode-title">
        <h2 id="mode-title" className="sr-only">Mode</h2>
        <div role="radiogroup" aria-label="Mode" className="mode-options" onKeyDown={radioGroupKeys}>
          {options.filter(o => demoEnabled || o.value === 'live').map(o => (
            <button key={o.value} type="button" role="radio" aria-checked={mode === o.value} tabIndex={mode === o.value ? 0 : -1} className={`mode-option ${o.value} ${mode === o.value ? 'selected gborder' : ''}`} onClick={() => setMode(o.value)}>
              <span className="mode-option-icon">{o.icon}</span><b>{o.title}</b><span>{o.body}</span>
              {mode === o.value && <StatusPill tone={o.value === 'demo' ? 'lav' : 'mint'}>Selected</StatusPill>}
            </button>
          ))}
        </div>
      </section>

      <section className="panel rise" style={{ '--i': 2 } as React.CSSProperties} aria-labelledby="conn-title">
        <h2 id="conn-title">Backend connection</h2>
        <dl className="kv">
          <div><dt>API URL</dt><dd><code>{apiUrl}</code></dd></div>
          <div><dt>Status</dt><dd>{mode === 'demo' ? <StatusPill tone="lav">Not used in demo mode</StatusPill>
            : health.state === 'online' ? <StatusPill tone="mint">Online · {health.activeRuns} active run{health.activeRuns === 1 ? '' : 's'}</StatusPill>
            : health.state === 'offline' ? <StatusPill tone="coral">Unreachable</StatusPill> : <StatusPill tone="amber">Checking…</StatusPill>}</dd></div>
          {mode === 'live' && health.state === 'offline' && <div><dt>Error</dt><dd>{health.error}</dd></div>}
        </dl>
        <p className="note">The backend address is set at build time with <code>NEXT_PUBLIC_TRACE_API_URL</code>. The backend must list this site&apos;s origin in its <code>CORS_ORIGINS</code>.</p>
        {mode === 'live' && <button className="tool-button" onClick={refreshHealth}>Check again</button>}
      </section>

      <section className="panel rise" style={{ '--i': 3 } as React.CSSProperties} aria-labelledby="not-title">
        <h2 id="not-title">What TRACE does not do yet</h2>
        <ul className="plain-list">
          <li>Sign-in and per-user data: every visitor sees every run.</li>
          <li>Fact checking (Stage 4) and the written report (Stage 5). Results are collected and judged evidence, not an answer.</li>
          <li>Cancelling a run once it has started.</li>
        </ul>
      </section>
    </>
  )
}
