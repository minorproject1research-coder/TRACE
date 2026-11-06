'use client'

// Last-resort boundary: renders when the root layout itself fails, so it brings its own <html>.
export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, minHeight: '100vh', display: 'grid', placeItems: 'center', background: '#050914', color: '#f3f6ff', fontFamily: 'system-ui, sans-serif' }}>
        <div role="alert" style={{ maxWidth: 440, padding: 24 }}>
          <h1 style={{ fontSize: 22, margin: '0 0 8px' }}>TRACE hit an unexpected error</h1>
          <p style={{ color: '#bcc7e0', lineHeight: 1.6 }}>Nothing you ran was lost: research runs continue on the server and can be reopened from Research history.</p>
          <button onClick={reset} style={{ marginTop: 12, padding: '10px 16px', borderRadius: 10, border: '1px solid #36497e', background: '#15224a', color: '#f3f6ff', cursor: 'pointer' }}>Reload the page</button>
        </div>
      </body>
    </html>
  )
}
