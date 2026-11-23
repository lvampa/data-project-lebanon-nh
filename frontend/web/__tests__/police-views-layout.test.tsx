import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { PoliceViews } from '@/components/police-views/police-views'
import type { StatsData } from '@/lib/types'

const stats: StatsData = {
  total: 0,
  generated_at: '2026-11-23T12:00:00Z',
  since: '2026-01-01',
  by_type: [],
  by_weekday: [],
  by_hour: [],
  mapped_total: 0,
}

// Everything above the map or the view: the eyebrow, the title, the tabs and the filters.
function header(): HTMLElement {
  const title = screen.getByRole('heading', { name: 'Police activity in Lebanon' })
  return title.parentElement as HTMLElement
}

describe('PoliceViews layout', () => {
  beforeEach(() => {
    // The views wait on activity.json; a fetch that never settles keeps them loading.
    vi.stubGlobal(
      'fetch',
      vi.fn(() => new Promise(() => {})),
    )
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('keeps the header the same width on every tab', () => {
    render(<PoliceViews addresses={[]} stats={stats} />)
    const onMap = header().className

    fireEvent.click(screen.getByRole('tab', { name: 'Places' }))

    expect(header().className).toBe(onMap)
    expect(header().parentElement?.className ?? '').not.toMatch(/w-screen|max-w-/)
  })

  // jsdom has no layout, so this pins the classes: sideways scroll for a small phone, and
  // room under the tabs for the active underline, so the row never scrolls down.
  it('lets the tabs scroll sideways but not down', () => {
    render(<PoliceViews addresses={[]} stats={stats} />)
    const tabs = screen.getByRole('tablist')
    expect(tabs).toHaveClass('overflow-x-auto', 'pb-px')
  })
})
