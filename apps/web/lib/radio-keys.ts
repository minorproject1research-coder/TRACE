import type { KeyboardEvent } from 'react'

/**
 * Arrow-key behaviour for a `role="radiogroup"` made of `role="radio"` buttons (WAI-ARIA radio group pattern):
 * arrows / Home / End move focus and select; only the checked radio is in the tab order (give it tabIndex 0, the others -1).
 * Attach to the group element: <div role="radiogroup" onKeyDown={radioGroupKeys}>.
 */
export function radioGroupKeys(e: KeyboardEvent<HTMLElement>) {
  const keys = ['ArrowRight', 'ArrowDown', 'ArrowLeft', 'ArrowUp', 'Home', 'End']
  if (!keys.includes(e.key)) return
  const radios = Array.from(e.currentTarget.querySelectorAll<HTMLElement>('[role="radio"]:not([disabled])'))
  if (radios.length === 0) return
  const current = radios.findIndex(r => r === document.activeElement)
  if (current === -1) return
  e.preventDefault()
  let next = current
  if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = (current + 1) % radios.length
  else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = (current - 1 + radios.length) % radios.length
  else if (e.key === 'Home') next = 0
  else next = radios.length - 1
  radios[next].focus()
  radios[next].click()
}
