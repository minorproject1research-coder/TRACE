import Link from 'next/link'

export default function NotFound() {
  return (
    <div className="state-box" style={{ marginTop: 40 }}>
      <div><b>Page not found</b><p>There is nothing at this address.</p><Link className="link-button" href="/">Back to overview</Link></div>
    </div>
  )
}
