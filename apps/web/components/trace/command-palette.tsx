'use client'

import { useRouter } from 'next/navigation'
import { useEffect, useMemo, useRef, useState } from 'react'
import { FileText, History, LayoutDashboard, Plus, Search, Settings2 } from 'lucide-react'
import { statusLabel } from '@/lib/format'
import { useMode } from '@/lib/mode'
import type { RunSummary } from '@/lib/trace-types'

type Item = { key: string; label: string; hint: string; icon: React.ReactNode; run: () => void }

export function CommandPalette({ open, onClose, onNewResearch }: { open: boolean; onClose: () => void; onNewResearch: () => void }) {
  const ref = useRef<HTMLDialogElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const router = useRouter()
  const { api } = useMode()
  const [query, setQuery] = useState('')
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [loadError, setLoadError] = useState(false)
  const [active, setActive] = useState(0)

  useEffect(() => {
    const d = ref.current
    if (!d) return
    if (open && !d.open) {
      d.showModal()
      setQuery(''); setActive(0); setLoadError(false)
      api.list(30).then(setRuns, () => { setRuns([]); setLoadError(true) })
      requestAnimationFrame(() => inputRef.current?.focus())
    }
    if (!open && d.open) d.close()
  }, [open, api])

  const items = useMemo<Item[]>(() => {
    const go = (href: string) => () => { onClose(); router.push(href) }
    const pages: Item[] = [
      { key: 'p-new', label: 'New research', hint: 'Start a question', icon: <Plus size={16} />, run: () => { onClose(); onNewResearch() } },
      { key: 'p-over', label: 'Overview', hint: 'Page', icon: <LayoutDashboard size={16} />, run: go('/') },
      { key: 'p-hist', label: 'Research history', hint: 'Page', icon: <History size={16} />, run: go('/history') },
      { key: 'p-set', label: 'Settings', hint: 'Page and mode', icon: <Settings2 size={16} />, run: go('/settings') },
    ]
    const found: Item[] = runs.map(r => ({ key: r.id, label: r.question, hint: statusLabel[r.status], icon: <FileText size={16} />, run: go(`/research/${encodeURIComponent(r.id)}`) }))
    const q = query.trim().toLowerCase()
    return [...pages, ...found].filter(i => !q || i.label.toLowerCase().includes(q) || i.hint.toLowerCase().includes(q))
  }, [runs, query, router, onClose, onNewResearch])

  useEffect(() => setActive(0), [query])

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive(a => Math.min(items.length - 1, a + 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(a => Math.max(0, a - 1)) }
    else if (e.key === 'Enter') { e.preventDefault(); items[active]?.run() }
  }

  return (
    <dialog ref={ref} className="palette" aria-label="Search and jump to" onClose={onClose} onClick={e => { if (e.target === ref.current) onClose() }}>
      <div className="palette-box" onKeyDown={onKeyDown}>
        <div className="palette-input"><Search size={17} aria-hidden="true" />
          <input ref={inputRef} value={query} onChange={e => setQuery(e.target.value)} placeholder="Search pages and past research…" aria-label="Search pages and past research" role="combobox" aria-expanded="true" aria-controls="palette-list" aria-activedescendant={items[active] ? `pal-${items[active].key}` : undefined} />
          <kbd>Esc</kbd>
        </div>
        <ul id="palette-list" role="listbox" className="palette-list">
          {items.length === 0 && <li className="palette-empty">No matches</li>}
          {items.map((it, i) => (
            <li key={it.key} id={`pal-${it.key}`} role="option" aria-selected={i === active} className={i === active ? 'active' : ''} onMouseEnter={() => setActive(i)} onClick={it.run}>
              {it.icon}<span className="palette-label">{it.label}</span><span className="palette-hint">{it.hint}</span>
            </li>
          ))}
        </ul>
        {loadError && <p className="palette-note">Could not load past research from the backend.</p>}
      </div>
    </dialog>
  )
}
