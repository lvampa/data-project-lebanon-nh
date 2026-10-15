import { describe, it, expect, vi } from 'vitest'
import { render, screen, act, fireEvent } from '@testing-library/react'
import { IncidentsTable } from '@/components/incidents-table'
import type { Incident } from '@/lib/types'

// Default mock — overridden per-test via vi.mocked where needed
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn() }),
  useSearchParams: vi.fn(() => new URLSearchParams()),
  usePathname: () => '/incidents',
}))

function makeIncident(overrides?: Partial<Incident>): Incident {
  return {
    case_number: '2024-001',
    reported_at: '2024-01-15T14:30:00',
    call_source: 'Phone',
    incident_type: 'THEFT',
    disposition: 'Report taken',
    location: '1 Main St',
    officer: 'Smith',
    reference_number: null,
    source_url: 'https://example.com/log.pdf',
    ...overrides,
  }
}

function makeIncidents(count: number, overrides?: Partial<Incident>): Incident[] {
  return Array.from({ length: count }, (_, i) =>
    makeIncident({ case_number: `2024-${String(i + 1).padStart(3, '0')}`, ...overrides }),
  )
}

// Grab the mocked useSearchParams so tests can override it
import { useSearchParams } from 'next/navigation'

describe('IncidentsTable', () => {
  it('renders incident rows from the passed array', () => {
    vi.mocked(useSearchParams).mockReturnValue(new URLSearchParams())
    const incidents = [
      makeIncident({ case_number: '2024-001', incident_type: 'THEFT', officer: 'Smith' }),
      makeIncident({ case_number: '2024-002', incident_type: 'ASSAULT', officer: 'Jones' }),
    ]
    render(<IncidentsTable incidents={incidents} />)
    expect(screen.getByText('2024-001')).toBeInTheDocument()
    expect(screen.getByText('2024-002')).toBeInTheDocument()
    expect(screen.getByText('THEFT')).toBeInTheDocument()
    expect(screen.getByText('ASSAULT')).toBeInTheDocument()
  })

  it('filters by incident_type from search params (case-insensitive)', () => {
    vi.mocked(useSearchParams).mockReturnValue(new URLSearchParams('incident_type=theft'))
    const incidents = [
      makeIncident({ case_number: '2024-001', incident_type: 'THEFT' }),
      makeIncident({ case_number: '2024-002', incident_type: 'ASSAULT' }),
    ]
    render(<IncidentsTable incidents={incidents} />)
    expect(screen.getByText('2024-001')).toBeInTheDocument()
    expect(screen.queryByText('2024-002')).not.toBeInTheDocument()
  })

  it('filters by officer from search params (case-insensitive)', () => {
    vi.mocked(useSearchParams).mockReturnValue(new URLSearchParams('officer=smith'))
    const incidents = [
      makeIncident({ case_number: '2024-001', officer: 'Smith' }),
      makeIncident({ case_number: '2024-002', officer: 'Jones' }),
    ]
    render(<IncidentsTable incidents={incidents} />)
    expect(screen.getByText('2024-001')).toBeInTheDocument()
    expect(screen.queryByText('2024-002')).not.toBeInTheDocument()
  })

  it('shows correct result count in the "N incidents" line', () => {
    vi.mocked(useSearchParams).mockReturnValue(new URLSearchParams('incident_type=theft'))
    const incidents = [
      makeIncident({ incident_type: 'THEFT' }),
      makeIncident({ case_number: '2024-002', incident_type: 'ASSAULT' }),
      makeIncident({ case_number: '2024-003', incident_type: 'THEFT' }),
    ]
    render(<IncidentsTable incidents={incidents} />)
    expect(screen.getByText('2 incidents')).toBeInTheDocument()
  })

  it('does not show pagination when all results fit on one page (≤50)', () => {
    vi.mocked(useSearchParams).mockReturnValue(new URLSearchParams())
    render(<IncidentsTable incidents={makeIncidents(50)} />)
    expect(screen.queryByText(/Prev/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Next/)).not.toBeInTheDocument()
  })

  it('shows pagination when results exceed one page (>50 items)', () => {
    vi.mocked(useSearchParams).mockReturnValue(new URLSearchParams())
    render(<IncidentsTable incidents={makeIncidents(51)} />)
    expect(screen.getByText(/Next/)).toBeInTheDocument()
    expect(screen.getByText(/Page 1 of 2/)).toBeInTheDocument()
  })

  it('page resets to 1 when filter changes', async () => {
    vi.mocked(useSearchParams).mockReturnValue(new URLSearchParams())
    const incidents = makeIncidents(101)
    const { rerender } = render(<IncidentsTable incidents={incidents} />)
    fireEvent.click(screen.getByText(/Next/))
    expect(screen.getByText(/Page 2 of 3/)).toBeInTheDocument()

    vi.mocked(useSearchParams).mockReturnValue(new URLSearchParams('incident_type=theft'))
    await act(async () => {
      rerender(<IncidentsTable incidents={incidents} />)
    })

    expect(screen.getByText(/Page 1 of 3/)).toBeInTheDocument()
  })
})
