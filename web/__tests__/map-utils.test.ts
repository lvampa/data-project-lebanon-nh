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

  it('uses normalized_address in label', () => {
    expect(addressToMarker(ADDR).label).toContain('1 Main Street, Lebanon, NH')
  })

  it('includes incident count in label', () => {
    expect(addressToMarker(ADDR).label).toContain('5')
  })

  it('falls back to raw_address when normalized_address is null', () => {
    const addr: Address = { ...ADDR, normalized_address: null }
    expect(addressToMarker(addr).label).toContain('1 Main St')
  })
})
