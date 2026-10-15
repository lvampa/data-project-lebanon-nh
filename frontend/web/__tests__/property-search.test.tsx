import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { PropertySearch } from '@/components/property-search'
import type { PropertyRecord } from '@/lib/types'

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn() }),
  useSearchParams: vi.fn(() => new URLSearchParams()),
  usePathname: () => '/properties',
}))

function makeProperty(overrides?: Partial<PropertyRecord>): PropertyRecord {
  return {
    parcel_id: 'NH-001',
    location: '1 Main St',
    owner: 'John Smith',
    owner_address: null,
    land_use: 'Residential',
    lot_size_acres: 0.25,
    year_built: 1980,
    building_sqft: 1200,
    assessed_land: 50000,
    assessed_building: 150000,
    assessed_total: 200000,
    assessment_year: 2023,
    detail_url: 'https://example.com',
    ...overrides,
  }
}

function makeProperties(count: number, overrides?: Partial<PropertyRecord>): PropertyRecord[] {
  return Array.from({ length: count }, (_, i) =>
    makeProperty({ parcel_id: `NH-${String(i + 1).padStart(3, '0')}`, ...overrides }),
  )
}

import { useSearchParams, type ReadonlyURLSearchParams } from 'next/navigation'

function mockSearchParams(query = '') {
  vi.mocked(useSearchParams).mockReturnValue(new URLSearchParams(query) as ReadonlyURLSearchParams)
}

describe('PropertySearch', () => {
  it('renders the search input', () => {
    mockSearchParams()
    render(<PropertySearch properties={[]} />)
    expect(screen.getByPlaceholderText('Search by address or owner…')).toBeInTheDocument()
  })

  it('renders all properties when no filter is active', () => {
    mockSearchParams()
    const properties = [
      makeProperty({ parcel_id: 'NH-001', location: '1 Main St', owner: 'Alice' }),
      makeProperty({ parcel_id: 'NH-002', location: '2 Elm St', owner: 'Bob' }),
    ]
    render(<PropertySearch properties={properties} />)
    expect(screen.getByText('1 Main St')).toBeInTheDocument()
    expect(screen.getByText('2 Elm St')).toBeInTheDocument()
  })

  it('filters properties by location (case-insensitive, partial match)', () => {
    mockSearchParams('q=main')
    const properties = [
      makeProperty({ parcel_id: 'NH-001', location: '1 Main St', owner: 'Alice' }),
      makeProperty({ parcel_id: 'NH-002', location: '2 Elm St', owner: 'Bob' }),
    ]
    render(<PropertySearch properties={properties} />)
    expect(screen.getByText('1 Main St')).toBeInTheDocument()
    expect(screen.queryByText('2 Elm St')).not.toBeInTheDocument()
  })

  it('filters properties by owner (case-insensitive, partial match)', () => {
    mockSearchParams('q=alice')
    const properties = [
      makeProperty({ parcel_id: 'NH-001', location: '1 Main St', owner: 'Alice Johnson' }),
      makeProperty({ parcel_id: 'NH-002', location: '2 Elm St', owner: 'Bob Smith' }),
    ]
    render(<PropertySearch properties={properties} />)
    expect(screen.getByText('Alice Johnson')).toBeInTheDocument()
    expect(screen.queryByText('Bob Smith')).not.toBeInTheDocument()
  })

  it('shows correct result count', () => {
    mockSearchParams('q=main')
    const properties = [
      makeProperty({ parcel_id: 'NH-001', location: '1 Main St' }),
      makeProperty({ parcel_id: 'NH-002', location: '2 Elm St' }),
      makeProperty({ parcel_id: 'NH-003', location: '3 Main Ave' }),
    ]
    render(<PropertySearch properties={properties} />)
    expect(screen.getByText('2 properties')).toBeInTheDocument()
  })

  it('does not show pagination when results fit on one page (≤50)', () => {
    mockSearchParams()
    render(<PropertySearch properties={makeProperties(50)} />)
    expect(screen.queryByText(/Prev/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Next/)).not.toBeInTheDocument()
  })

  it('shows pagination when results exceed 50', () => {
    mockSearchParams()
    render(<PropertySearch properties={makeProperties(51)} />)
    expect(screen.getByText(/Next/)).toBeInTheDocument()
    expect(screen.getByText(/Page 1 of 2/)).toBeInTheDocument()
  })

  it('page resets to 1 when the query changes in the URL', () => {
    mockSearchParams()
    const properties = makeProperties(101)
    const { rerender } = render(<PropertySearch properties={properties} />)
    fireEvent.click(screen.getByText(/Next/))
    expect(screen.getByText(/Page 2 of 3/)).toBeInTheDocument()

    mockSearchParams('q=main')
    rerender(<PropertySearch properties={properties} />)

    expect(screen.getByText(/Page 1 of 3/)).toBeInTheDocument()
  })
})
