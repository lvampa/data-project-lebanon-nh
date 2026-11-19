import { describe, expect, it } from 'vitest'
import { CALLS_CAP, pinName, pinsGeoJson } from '@/lib/police-map/map-style'
import type { Address } from '@/lib/types'

const FORD: Address = {
  id: 'lebanon-ford-90-miracle-mile',
  kind: 'place',
  raw_address: 'LEBANON FORD',
  normalized_address: 'Lebanon Ford, 90 Miracle Mile',
  count: 12,
  traffic_count: 3,
  lat: 43.64,
  lng: -72.25,
}

describe('pinsGeoJson', () => {
  it('makes one point per address, with longitude first', () => {
    const { features } = pinsGeoJson([FORD])

    expect(features).toHaveLength(1)
    expect(features[0].geometry.coordinates).toEqual([-72.25, 43.64])
  })

  it('carries the id, the name and the call count the map draws from', () => {
    const [feature] = pinsGeoJson([FORD]).features

    expect(feature.properties).toEqual({
      id: 'lebanon-ford-90-miracle-mile',
      name: 'Lebanon Ford, 90 Miracle Mile',
      n: 12,
    })
  })
})

describe('pinName', () => {
  it('falls back to the raw address when there is no normalized one', () => {
    expect(pinName({ ...FORD, normalized_address: null })).toBe('LEBANON FORD')
  })
})

describe('CALLS_CAP', () => {
  it('is 3000, so the busiest place does not hide the rest', () => {
    expect(CALLS_CAP).toBe(3000)
  })
})
