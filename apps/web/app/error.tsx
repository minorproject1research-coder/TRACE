'use client'

import { ErrorState } from '@/components/trace/states'

export default function RouteError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <div style={{ marginTop: 40 }}><ErrorState title="This page crashed" message={error.message || 'An unexpected error occurred.'} onRetry={reset} /></div>
}
