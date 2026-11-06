'use client'

import { Component, type ReactNode } from 'react'
import { ErrorState } from './states'

/**
 * Keeps a rendering error inside the part of the page it came from. The run page's tabs show data produced by language models and by a
 * pipeline that changes; if one record has a shape the UI did not expect, only that tab says so: the rest of the page keeps working.
 * `resetKey` changes (for example the selected tab) clear the error.
 */
export class Boundary extends Component<{ label: string; resetKey?: string; children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null }

  static getDerivedStateFromError(error: Error) { return { error } }

  componentDidUpdate(prev: { resetKey?: string }) {
    if (prev.resetKey !== this.props.resetKey && this.state.error) this.setState({ error: null })
  }

  componentDidCatch(error: Error) { console.error(`[${this.props.label}] could not be displayed:`, error) }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="tab-scroll" role="region" aria-label={`${this.props.label} (error)`} tabIndex={0}>
        <ErrorState title={`${this.props.label} could not be displayed`} message={`${this.state.error.message || 'Unexpected data.'} The rest of the page is unaffected.`} onRetry={() => this.setState({ error: null })} />
      </div>
    )
  }
}
