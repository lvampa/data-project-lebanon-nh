import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { IncidentsFilters } from '@/components/incidents-filters'

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => '/incidents',
}))

describe('IncidentsFilters', () => {
  it('renders incident type input', () => {
    render(<IncidentsFilters />)
    expect(screen.getByPlaceholderText('Incident type…')).toBeInTheDocument()
  })

  it('renders officer input', () => {
    render(<IncidentsFilters />)
    expect(screen.getByPlaceholderText('Officer…')).toBeInTheDocument()
  })

  it('does not show clear button when no params active', () => {
    render(<IncidentsFilters />)
    expect(screen.queryByText('Clear')).not.toBeInTheDocument()
  })
})
