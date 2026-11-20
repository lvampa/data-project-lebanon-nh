import { describe, expect, it } from 'vitest'
import {
  CALLS_CAP,
  isTrafficOnly,
  pinCalls,
  pinName,
  pinsGeoJson,
} from '@/lib/police-map/map-style'
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
  precision: 'exact',
  street_id: null,
  hidden: false,
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
      w: 12,
      t: 0,
      a: 0,
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

describe('a place with traffic on its street and no calls of its own', () => {
  const corner: Address = { ...FORD, count: 0, traffic_count: 7 }

  it('is sized and shaded by its traffic', () => {
    expect(isTrafficOnly(corner)).toBe(true)
    expect(pinCalls(corner)).toBe(7)
    const [feature] = pinsGeoJson([corner]).features
    expect(feature.properties.n).toBe(0)
    expect(feature.properties.w).toBe(7)
    expect(feature.properties.t).toBe(1)
  })

  it('is not one for an ordinary place, or a place with nothing at all', () => {
    expect(isTrafficOnly(FORD)).toBe(false)
    expect(pinCalls(FORD)).toBe(12)
    expect(isTrafficOnly({ ...FORD, count: 0, traffic_count: 0 })).toBe(false)
  })
})
