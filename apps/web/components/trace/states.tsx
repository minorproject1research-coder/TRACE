import { AlertTriangle, Inbox, RefreshCw } from 'lucide-react'

export function Skeleton({ rows = 3, label = 'Loading' }: { rows?: number; label?: string }) {
  return (
    <div className="skeleton-stack" role="status" aria-live="polite" aria-label={label}>
      {Array.from({ length: rows }, (_, i) => <div className="skeleton" key={i} style={{ '--w': `${92 - i * 11}%` } as React.CSSProperties} />)}
      <span className="sr-only">{label}…</span>
    </div>
  )
}

export function ErrorState({ title = 'Something went wrong', message, onRetry, status }: { title?: string; message: string; onRetry?: () => void; status?: number }) {
  return (
    <div className="state-box error" role="alert">
      <AlertTriangle size={22} aria-hidden="true" />
      <div>
        <b>{title}{status ? <span className="code"> {status}</span> : null}</b>
        <p>{message}</p>
        {onRetry && <button className="tool-button" onClick={onRetry}><RefreshCw size={14} /> Try again</button>}
      </div>
    </div>
  )
}

export function EmptyState({ title, message, action }: { title: string; message: string; action?: React.ReactNode }) {
  return (
    <div className="state-box">
      <Inbox size={22} aria-hidden="true" />
      <div><b>{title}</b><p>{message}</p>{action}</div>
    </div>
  )
}
