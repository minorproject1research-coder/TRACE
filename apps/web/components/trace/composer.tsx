'use client'

import { useRouter } from 'next/navigation'
import { useEffect, useId, useRef, useState } from 'react'
import { ArrowUpRight, Play, Sparkles } from 'lucide-react'
import { useMode } from '@/lib/mode'
import { ApiError } from '@/lib/trace-types'
import { ErrorState } from './states'

// Limits enforced by the API (apps/api/config.py): 10-1000 characters after whitespace is collapsed.
const MIN = 10
const MAX = 1000

const examples = ['How reliable are AI-generated citations?', 'What drives battery degradation?', 'Compare open-source LLM licenses']
export function Composer() {
  const router = useRouter()
  const { api, mode } = useMode()
  const [question, setQuestion] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [touched, setTouched] = useState(false)
  const area = useRef<HTMLTextAreaElement>(null)
  const hintId = useId()

  // "New research" in the nav, the N shortcut and the palette all land here.
  useEffect(() => {
    const focus = () => { area.current?.focus({ preventScroll: false }); area.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }) }
    if (window.location.hash === '#new-research') setTimeout(focus, 50)
    window.addEventListener('trace:focus-composer', focus)
    return () => window.removeEventListener('trace:focus-composer', focus)
  }, [])

  const collapsed = question.replace(/\s+/g, ' ').trim()
  const tooShort = collapsed.length < MIN
  const tooLong = collapsed.length > MAX
  const invalid = tooShort || tooLong
  const showInvalid = touched && invalid

  const submit = async () => {
    setTouched(true)
    if (invalid || submitting) return
    setSubmitting(true); setError(null)
    try {
      const session = await api.create({ question: collapsed })
      router.push(`/research/${encodeURIComponent(session.id)}`)
    } catch (e) {
      setError(e instanceof ApiError ? e : new ApiError('Could not start the research. Try again.'))
      setSubmitting(false)
    }
  }

  return (
    <section id="new-research" className="composer ring rise" style={{ '--i': 2 } as React.CSSProperties} aria-labelledby="composer-title">
      <div className="composer-fx" aria-hidden="true"><div className="composer-glow" /></div>
      <div className="composer-top">
        <div>
          <div className="eyebrow" style={{ color: 'var(--cyan)' }}><Sparkles size={14} /> Start a new research thread</div>
          <h2 id="composer-title">What do you want to understand?</h2>
        </div>
        <span className={`mode-badge ${mode === 'live' ? 'live' : ''}`}>{mode === 'live' ? 'LIVE · REAL BACKEND' : 'DEMO · SAMPLE DATA'}</span>
      </div>

      <textarea
        ref={area} id="research-question" value={question} maxLength={MAX * 2}
        onChange={e => setQuestion(e.target.value)} onBlur={() => setTouched(true)}
        onKeyDown={e => { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); void submit() } }}
        placeholder="Ask a question worth investigating..." aria-label="Research question" aria-describedby={hintId} aria-invalid={showInvalid}
      />
      <div className="field-hint" id={hintId}>
        <span className={showInvalid ? 'err' : ''}>{tooLong ? `Too long: ${MAX} characters at most.` : showInvalid ? `Write at least ${MIN} characters so TRACE has something to investigate.` : 'Ctrl+Enter to start'}</span>
        <span className={tooLong ? 'err' : ''}>{collapsed.length} / {MAX}</span>
      </div>

      <div className="suggestions"><span>Try an example</span>{examples.map(item => <button type="button" className="chip" key={item} onClick={() => { setQuestion(item); setTouched(false); area.current?.focus() }}>{item}<ArrowUpRight size={13} /></button>)}</div>

      <div className="composer-controls">
        <p className="run-expectation">{mode === 'live' ? 'A real run takes about 15 to 25 minutes. You can leave the page and come back from Research history.' : 'A demo run takes about 13 seconds and produces fictional sample results.'}</p>
        <button type="button" className="start-button push" onClick={() => void submit()} disabled={submitting}>
          {submitting ? <span className="spinner dark" aria-hidden="true" /> : <Play size={15} fill="currentColor" />}
          {submitting ? 'Starting…' : 'Start research'}<span className="arrow" aria-hidden="true">↗</span>
        </button>
      </div>

      {error && <div style={{ marginTop: 16 }}><ErrorState title={error.status === 429 ? 'TRACE is busy' : 'Could not start the research'} message={error.message} status={error.status} onRetry={() => void submit()} /></div>}
    </section>
  )
}
