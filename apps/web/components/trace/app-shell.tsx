'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useCallback, useEffect, useState } from 'react'
import { ChevronRight, FileText, FlaskConical, FolderKanban, History, LayoutDashboard, Library, Menu, Plus, Radio, Search, Settings2, WifiOff } from 'lucide-react'
import { useMode } from '@/lib/mode'
import { CommandPalette } from './command-palette'

const NEW_RESEARCH_HREF = '/#new-research'

const nav = [
  { label: 'Overview', href: '/', icon: LayoutDashboard },
  { label: 'New research', href: NEW_RESEARCH_HREF, icon: Plus, kbd: 'N' },
  { label: 'Research history', href: '/history', icon: History },
] as const

// Not built on the backend yet (see docs/API_HANDOFF.md "Not built"): shown as disabled so nobody hunts for them.
const soon = [
  { label: 'Saved reports', icon: FileText },
  { label: 'Sources library', icon: Library },
  { label: 'Research projects', icon: FolderKanban },
] as const

function isActive(pathname: string, href: string) {
  if (href === NEW_RESEARCH_HREF) return false
  if (href === '/') return pathname === '/'
  return pathname === href || pathname.startsWith(href + '/')
}

function useCrumbs(pathname: string): string[] {
  const parts = pathname.split('/').filter(Boolean)
  if (parts.length === 0) return ['Overview']
  if (parts[0] === 'history') return ['Research history']
  if (parts[0] === 'settings') return ['Settings']
  if (parts[0] === 'research') return ['Research', parts[1] ? `Run ${decodeURIComponent(parts[1]).slice(0, 8)}` : '', parts[2] === 'report' ? 'Evidence report' : ''].filter(Boolean)
  return ['Not found']
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()
  const { ready, demoEnabled, mode, setMode, health, refreshHealth, apiUrl } = useMode()
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const crumbs = useCrumbs(pathname)

  useEffect(() => setMobileOpen(false), [pathname])

  const goNew = useCallback(() => {
    router.push(NEW_RESEARCH_HREF)
    window.dispatchEvent(new Event('trace:focus-composer'))
  }, [router])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setPaletteOpen(true); return }
      if (e.key === 'Escape' && mobileOpen) { setMobileOpen(false); return }
      const el = e.target as HTMLElement | null
      const typing = !!el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT' || el.isContentEditable)
      if (!typing && !e.metaKey && !e.ctrlKey && !e.altKey && e.key === 'n') { e.preventDefault(); goNew() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [mobileOpen, goNew])

  const statusText = mode === 'demo' ? 'Demo simulator' : health.state === 'online' ? 'API online' : health.state === 'offline' ? 'API unreachable' : 'Checking API…'
  const statusDetail = mode === 'demo' ? 'No backend in use' : health.state === 'online' ? `${health.activeRuns} active run${health.activeRuns === 1 ? '' : 's'}` : health.state === 'offline' ? apiUrl : apiUrl

  return (
    <>
      <div className="atmosphere" aria-hidden="true"><div className="blob b1" /><div className="blob b2" /><div className="blob b3" /><div className="grid" /></div>
      <a className="skip-link" href="#main">Skip to content</a>
      <div className="trace-app">
        {mobileOpen && <button className="sidebar-scrim" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />}
        <aside className={`sidebar ${collapsed ? 'collapsed' : ''} ${mobileOpen ? 'mobile-open' : ''}`}>
          <div className="brand">
            <button className="brand-toggle" onClick={() => setCollapsed(!collapsed)} aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}><img className="brand-logo" src="/trace-logo.png" alt="" width={36} height={36} /></button>
            <div className="brand-copy rail-sr"><strong>TRACE</strong><span>RESEARCH INTELLIGENCE</span></div>
          </div>

          <Link href="/settings" className={`mode-card ${mode}`} title={collapsed ? `${mode === 'demo' ? 'Demo' : 'Live'} mode` : undefined}>
            {mode === 'demo' ? <FlaskConical size={18} /> : <Radio size={18} />}
            <div className="mode-copy rail-sr"><b>{mode === 'demo' ? 'Demo mode' : 'Live mode'}</b><span>{mode === 'demo' ? 'Sample data only' : 'Real TRACE backend'}</span></div>
          </Link>

          <nav className="nav-list" aria-label="Primary navigation">
            <div className="nav-label rail-hide">Workspace</div>
            {nav.map(({ label, href, icon: Icon, ...rest }) => {
              const active = isActive(pathname, href)
              return (
                <Link key={label} href={href} className={`nav-item ${active ? 'gborder' : ''}`} aria-current={active ? 'page' : undefined} title={collapsed ? label : undefined}
                  onClick={href === NEW_RESEARCH_HREF ? () => window.dispatchEvent(new Event('trace:focus-composer')) : undefined}>
                  <Icon size={18} /><span className="nav-text rail-sr">{label}</span>
                  {'kbd' in rest && <span className="nav-kbd rail-hide" aria-hidden="true">{rest.kbd}</span>}
                </Link>
              )
            })}
            {soon.map(({ label, icon: Icon }) => (
              <button key={label} className="nav-item" disabled aria-disabled="true" title={`${label}: not built yet`}>
                <Icon size={18} /><span className="nav-text rail-sr">{label}</span><span className="nav-soon rail-hide">SOON</span>
              </button>
            ))}
            <div className="nav-label spaced rail-hide">Manage</div>
            <Link href="/settings" className={`nav-item ${isActive(pathname, '/settings') ? 'gborder' : ''}`} aria-current={isActive(pathname, '/settings') ? 'page' : undefined} title={collapsed ? 'Settings' : undefined}>
              <Settings2 size={18} /><span className="nav-text rail-sr">Settings</span>
            </Link>
          </nav>

          <div className="sidebar-bottom">
            <div className="system-status" role="status">
              <span className={`live-dot ${mode === 'demo' ? 'lav' : health.state === 'offline' ? 'bad' : health.state === 'checking' ? 'wait' : ''}`} />
              <div className="rail-sr"><b>{statusText}</b><small>{statusDetail}</small></div>
            </div>
            <div className="local-note rail-hide"><span>Single local workspace</span><small>No sign-in or accounts yet</small></div>
          </div>
        </aside>

        <div className="main-shell">
          <header className="topbar">
            <button className="icon-button mobile-menu" onClick={() => setMobileOpen(!mobileOpen)} aria-label="Toggle navigation" aria-expanded={mobileOpen}><Menu size={20} /></button>
            <nav className="breadcrumbs" aria-label="Breadcrumb">
              <span>Workspace</span>
              {crumbs.map((c, i) => <span className="crumb" key={c + i}><ChevronRight size={14} aria-hidden="true" />{i === crumbs.length - 1 ? <b aria-current="page">{c}</b> : <span>{c}</span>}</span>)}
            </nav>
            <div className="topbar-actions">
              <span className={`mode-badge ${mode === 'live' ? 'live' : ''}`}>{mode === 'demo' ? 'DEMO' : 'LIVE'}</span>
              <button className="icon-button search-button" onClick={() => setPaletteOpen(true)} aria-keyshortcuts="Control+K"><Search size={16} /><span>Search</span><kbd>Ctrl K</kbd></button>
            </div>
          </header>

          {mode === 'demo' && (
            <div className="banner demo" role="status">
              <FlaskConical size={16} aria-hidden="true" />
              <p><b>Demo mode.</b> Everything you see is fictional sample data from a browser-side simulator. Nothing runs on the TRACE backend.</p>
              <button className="link-button" onClick={() => setMode('live')}>Switch to live</button>
            </div>
          )}
          {mode === 'live' && health.state === 'offline' && (
            <div className="banner offline" role="alert">
              <WifiOff size={16} aria-hidden="true" />
              <p><b>Cannot reach the TRACE backend</b> at <code>{apiUrl}</code>. Check that it is running, then retry.</p>
              <button className="link-button" onClick={refreshHealth}>Retry</button>
              {demoEnabled && <button className="link-button muted" onClick={() => setMode('demo')}>Use demo mode</button>}
            </div>
          )}

          <main id="main" className="content" tabIndex={-1}>{ready ? children : null}</main>
          <footer className="footer"><span>TRACE <i>·</i> Research Intelligence</span><span>{mode === 'demo' ? 'Demo mode · sample data' : `Live · ${apiUrl}`}</span></footer>
        </div>
      </div>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} onNewResearch={goNew} />
    </>
  )
}
