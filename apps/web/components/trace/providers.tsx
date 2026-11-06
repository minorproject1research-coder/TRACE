'use client'

import { ModeProvider } from '@/lib/mode'
import { AppShell } from './app-shell'

export function Providers({ children }: { children: React.ReactNode }) {
  return <ModeProvider><AppShell>{children}</AppShell></ModeProvider>
}
