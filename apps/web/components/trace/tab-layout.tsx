/**
 * Layout of a tab inside the run workspace: the controls stay put and only the list scrolls.
 *   <TabFixed>  filters, funnel, view switcher: always visible
 *   <TabScroll> the list: scrolls on its own and does not chain into the page scroll
 * The scrolling region is focusable (tabIndex 0, labelled) so keyboard users can scroll it with the arrow keys.
 */
export function TabFixed({ children }: { children: React.ReactNode }) {
  return <div className="tab-fixed">{children}</div>
}

export function TabScroll({ label, children, scrollRef }: { label: string; children: React.ReactNode; scrollRef?: React.Ref<HTMLDivElement> }) {
  return <div className="tab-scroll" tabIndex={0} role="region" aria-label={label} ref={scrollRef}>{children}</div>
}
