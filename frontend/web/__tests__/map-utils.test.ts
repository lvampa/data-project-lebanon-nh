import { describe, it, expect } from 'vitest'
import { addressToMarker } from '@/lib/map-utils'
import type { Address } from '@/lib/types'

const ADDR: Address = {
  raw_address: '1 Main St',
  normalized_address: '1 Main Street, Lebanon, NH',
  count: 5,
  lat: 43.642,
  lng: -72.252,
}

describe('addressToMarker', () => {
  it('returns lngLat as [lng, lat] (MapLibre order)', () => {
    expect(addressToMarker(ADDR).lngLat).toEqual([-72.252, 43.642])
  })

  it('uses normalized_address in the popup', () => {
    expect(addressToMarker(ADDR).popup.textContent).toContain('1 Main Street, Lebanon, NH')
  })

  it('includes the incident count in the popup', () => {
    expect(addressToMarker(ADDR).popup.textContent).toContain('5 incidents')
  })

  it('uses the singular for one incident', () => {
    expect(addressToMarker({ ...ADDR, count: 1 }).popup.textContent).toContain('1 incident')
  })

  it('falls back to raw_address when normalized_address is null', () => {
    const addr: Address = { ...ADDR, normalized_address: null }
    expect(addressToMarker(addr).popup.textContent).toContain('1 Main St')
  })

  it('renders a scraped address as text, not markup', () => {
    const payload = '<img src=x onerror=alert(1)>'
    const { popup } = addressToMarker({ ...ADDR, normalized_address: payload })

    expect(popup.querySelector('img')).toBeNull()
    expect(popup.querySelector('strong')?.textContent).toBe(payload)
  })
})
