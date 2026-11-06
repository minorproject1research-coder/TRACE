import { useId } from 'react'

/** The TRACE mark: three source nodes joined by a signal path. */
export function TraceMark({ size = 30 }: { size?: number }) {
  const id = useId()
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id={`${id}-g`} x1="4" y1="40" x2="44" y2="8" gradientUnits="userSpaceOnUse">
          <stop stopColor="#4f7dff" />
          <stop offset="1" stopColor="#3fe0f2" />
        </linearGradient>
      </defs>
      <path d="M9 31 L24 12 L39 36" stroke={`url(#${id}-g)`} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="9" cy="31" r="5" fill="#070c1a" stroke="#4f7dff" strokeWidth="2.4" />
      <circle cx="24" cy="12" r="5" fill="#070c1a" stroke="#3fe0f2" strokeWidth="2.4" />
      <circle cx="39" cy="36" r="5" fill="#7dffc4" />
    </svg>
  )
}
