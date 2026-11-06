export type PillTone = 'neutral' | 'mint' | 'amber' | 'blue' | 'lav' | 'coral'

export function StatusPill({ children, tone = 'neutral' }: { children: React.ReactNode; tone?: PillTone }) {
  return (
    <span className={`status-pill ${tone}`}>
      <span className="status-dot" aria-hidden="true" />
      {children}
    </span>
  )
}
