'use client'

import { ChevronRight } from 'lucide-react'
import { useId, useState } from 'react'

// A disclosure ("collapse bar"): a real <button aria-expanded aria-controls> that shows or hides a region. The state is visible on the bar (the chevron turns and the
// word Show / Hide changes), the button is reachable and operable with the keyboard, and the hidden region is `hidden`, so a screen reader skips it while it is closed.
// Styled like the .fold panels (app/globals.css, .wr-fold / .wr-bar). No animation of the height: nothing moves unexpectedly, and `prefers-reduced-motion` is respected.

export function FoldBar({ controls, open, onToggle, small, children }: { controls: string; open: boolean; onToggle: () => void; small?: boolean; children: React.ReactNode }) {
  return (
    <button type="button" className={`wr-bar${small ? ' small' : ''}`} aria-expanded={open} aria-controls={controls} onClick={onToggle}>
      <ChevronRight size={small ? 13 : 16} className="wr-chev" aria-hidden="true" />
      <span className="wr-bar-body">{children}</span>
      <span className="wr-bar-state" aria-hidden="true">{open ? 'Hide' : 'Show'}</span>
    </button>
  )
}

/** One bar with its region. Uncontrolled (`defaultOpen`) or controlled (`open` + `onOpenChange`). `heading` puts the bar inside an h2 / h3 (the button is the content of the heading). */
export function Fold({ title, meta, open, onOpenChange, defaultOpen = false, heading, small, className = '', children }: {
  title: React.ReactNode; meta?: React.ReactNode; open?: boolean; onOpenChange?: (open: boolean) => void; defaultOpen?: boolean; heading?: 2 | 3 | 4; small?: boolean; className?: string; children: React.ReactNode
}) {
  const [own, setOwn] = useState(defaultOpen)
  const rid = useId()
  const isOpen = open ?? own
  const toggle = () => { const next = !isOpen; if (open === undefined) setOwn(next); onOpenChange?.(next) }
  const bar = <FoldBar controls={rid} open={isOpen} onToggle={toggle} small={small}><span className="wr-bar-title">{title}</span>{meta && <span className="wr-bar-sub">{meta}</span>}</FoldBar>
  const H = heading ? (`h${heading}` as 'h2') : null
  return (
    <div className={`wr-fold${small ? ' small' : ''} ${className}`.trim()}>
      {H ? <H className="wr-fold-h">{bar}</H> : bar}
      <div id={rid} className="wr-fold-body" hidden={!isOpen}>{children}</div>
    </div>
  )
}
