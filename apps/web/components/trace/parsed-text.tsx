'use client'

import { useEffect, useImperativeHandle, useMemo, useRef, useState, forwardRef } from 'react'
import type { Span } from '@/lib/trace-types'

/** A highlighted range; `id` is the index of the finding it belongs to. */
export type Mark = Span & { id: number }
export type ParsedTextHandle = { jumpToMark: (id: number) => void; jumpToHeading: (heading: string) => void }

type Block = { start: number; end: number; text: string; kind: 'heading' | 'table' | 'list' | 'paragraph'; level: number }

const INITIAL_BLOCKS = 70
const MORE_BLOCKS = 150

/** Split the parser's markdown into blocks at blank lines, remembering where each block sits in the original string. */
function toBlocks(text: string): Block[] {
  const blocks: Block[] = []
  const re = /\n[ \t]*\n+/g
  let last = 0
  const push = (start: number, end: number) => {
    const raw = text.slice(start, end)
    if (!raw.trim()) return
    const heading = /^(#{1,6})[ \t]+/.exec(raw)
    const lines = raw.split('\n')
    const kind: Block['kind'] = heading ? 'heading' : lines[0].trimStart().startsWith('|') ? 'table' : lines.every(l => /^\s*([-*•]|\d+[.)])\s+/.test(l)) ? 'list' : 'paragraph'
    blocks.push({ start, end, text: raw, kind, level: heading ? heading[1].length : 0 })
  }
  for (let m = re.exec(text); m; m = re.exec(text)) { push(last, m.index); last = m.index + m[0].length }
  push(last, text.length)
  return blocks
}

/** Display-only clean-up of parser artefacts. It never changes what offsets refer to: it is applied to rendered pieces only. */
const clean = (s: string) => s.replace(/<!--\s*image\s*-->/gi, '[figure]').replace(/<!--[\s\S]*?-->/g, '')

function renderRanged(text: string, blockStart: number, marks: Mark[], active: number | null) {
  const end = blockStart + text.length
  const mine = marks.filter(m => m.end > blockStart && m.start < end).sort((a, b) => a.start - b.start)
  if (mine.length === 0) return clean(text)
  const out: React.ReactNode[] = []
  let pos = blockStart
  mine.forEach((m, i) => {
    const s = Math.max(m.start, pos), e = Math.min(m.end, end)
    if (e <= s) return
    if (s > pos) out.push(clean(text.slice(pos - blockStart, s - blockStart)))
    out.push(<mark key={i} id={`mark-${m.id}-${i}`} data-mark={m.id} className={active === m.id ? 'active' : ''}>{clean(text.slice(s - blockStart, e - blockStart))}</mark>)
    pos = e
  })
  if (pos < end) out.push(clean(text.slice(pos - blockStart)))
  return out
}

function renderTable(raw: string) {
  const isSeparator = (l: string) => /^[\s|:-]+$/.test(l) && l.includes('-')       // |---|:--:|
  const rows = raw.split('\n').filter(l => l.trim().startsWith('|') && !isSeparator(l))
  const cells = rows.map(r => r.trim().replace(/^\||\|$/g, '').split('|').map(c => clean(c.trim())))
  if (cells.length === 0) return null
  const [head, ...body] = cells
  return (
    <div className="table-wrap" tabIndex={0} role="region" aria-label="Table from the paper">
      <table><thead><tr>{head.map((c, i) => <th key={i} scope="col">{c}</th>)}</tr></thead>
        <tbody>{body.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{c}</td>)}</tr>)}</tbody></table>
    </div>
  )
}

export const ParsedText = forwardRef<ParsedTextHandle, { text: string; marks: Mark[]; active: number | null }>(function ParsedText({ text, marks, active }, ref) {
  const blocks = useMemo(() => toBlocks(text), [text])
  const [visible, setVisible] = useState(INITIAL_BLOCKS)
  const pending = useRef<string | null>(null)       // element id to scroll to once it has been rendered
  const rootRef = useRef<HTMLDivElement>(null)

  const blockIndexAt = (offset: number) => {
    let lo = 0, hi = blocks.length - 1
    while (lo < hi) { const mid = (lo + hi) >> 1; if (blocks[mid].end <= offset) lo = mid + 1; else hi = mid }
    return lo
  }

  useImperativeHandle(ref, () => ({
    jumpToMark(id) {
      const m = marks.filter(x => x.id === id).sort((a, b) => a.start - b.start)[0]
      if (!m) return
      const idx = blockIndexAt(m.start)
      pending.current = `mark:${id}`
      setVisible(v => Math.max(v, idx + 12))
      requestAnimationFrame(() => scrollPending())
    },
    jumpToHeading(heading) {
      const want = heading.trim().toLowerCase()
      const idx = blocks.findIndex(b => b.kind === 'heading' && b.text.replace(/^#{1,6}[ \t]+/, '').trim().toLowerCase() === want)
      if (idx < 0) return
      pending.current = `block:${idx}`
      setVisible(v => Math.max(v, idx + 12))
      requestAnimationFrame(() => scrollPending())
    },
  }))

  const scrollPending = () => {
    const p = pending.current
    const root = rootRef.current
    if (!p || !root) return
    const el = p.startsWith('mark:') ? root.querySelector<HTMLElement>(`[data-mark="${p.slice(5)}"]`) : root.querySelector<HTMLElement>(`#blk-${p.slice(6)}`)
    if (el) { pending.current = null; el.scrollIntoView({ block: 'center', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' }) }
  }
  useEffect(scrollPending, [visible, marks])

  const shown = blocks.slice(0, visible)
  return (
    <div className="parsed-text" ref={rootRef}>
      {shown.map((b, i) => {
        const id = `blk-${i}`
        if (b.kind === 'heading') {
          const body = renderRanged(b.text.replace(/^#{1,6}[ \t]+/, ''), b.start + (b.text.length - b.text.replace(/^#{1,6}[ \t]+/, '').length), marks, active)
          const level = Math.min(6, Math.max(2, b.level + 1))        // the paper's title is level 2 here: the page already has an h1
          const Tag = `h${level}` as 'h2'
          return <Tag key={i} id={id} className="pt-h">{body}</Tag>
        }
        if (b.kind === 'table') {
          const hasMark = marks.some(m => m.end > b.start && m.start < b.end)
          return hasMark ? <pre key={i} id={id} className="pt-pre">{renderRanged(b.text, b.start, marks, active)}</pre> : <div key={i} id={id}>{renderTable(b.text)}</div>
        }
        if (b.kind === 'list') return <ul key={i} id={id} className="pt-list">{b.text.split('\n').map((l, j) => <li key={j}>{clean(l.replace(/^\s*([-*•]|\d+[.)])\s+/, ''))}</li>)}</ul>
        return <p key={i} id={id} className="pt-p">{renderRanged(b.text, b.start, marks, active)}</p>
      })}
      {blocks.length > visible && (
        <button type="button" className="tool-button more" onClick={() => setVisible(v => v + MORE_BLOCKS)}>
          Show more ({blocks.length - visible} sections of text remaining)
        </button>
      )}
    </div>
  )
})
