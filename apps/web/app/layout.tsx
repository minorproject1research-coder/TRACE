import type { Metadata, Viewport } from 'next'
import { Bricolage_Grotesque, Geist, Geist_Mono, Newsreader } from 'next/font/google'
import { Providers } from '@/components/trace/providers'
import './globals.css'

const display = Bricolage_Grotesque({ subsets: ['latin'], variable: '--font-display', display: 'swap' })
const sans = Geist({ subsets: ['latin'], variable: '--font-sans', display: 'swap' })
const mono = Geist_Mono({ subsets: ['latin'], variable: '--font-mono', display: 'swap' })
const serif = Newsreader({ subsets: ['latin'], style: ['italic'], weight: ['500'], variable: '--font-serif', display: 'swap' })

export const metadata: Metadata = {
  title: { default: 'TRACE — Research Intelligence', template: '%s · TRACE' },
  description: 'Find the signal. Verify the evidence. TRACE is an evidence-first research intelligence workspace.',
  icons: {
    icon: [
      { url: '/icon-light-32x32.png', media: '(prefers-color-scheme: light)' },
      { url: '/icon-dark-32x32.png', media: '(prefers-color-scheme: dark)' },
      { url: '/icon.svg', type: 'image/svg+xml' },
    ],
    apple: '/apple-icon.png',
  },
}

// Midnight Signal is a dark-only system.
export const viewport: Viewport = {
  colorScheme: 'dark',
  themeColor: '#050914',
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable} ${mono.variable} ${serif.variable}`}>
      <body className="antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
