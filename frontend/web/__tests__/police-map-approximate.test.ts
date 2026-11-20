import { describe, expect, it } from 'vitest'
import {
  hiddenCallsByStreet,
  isApproximatePlace,
  placesOnStreet,
  streetNameOf,
  streetPinOf,
} from '@/lib/police-map/approximate'
import { approximateLine, onStreetHeading } from '@/lib/police-map/format'
import { pinsGeoJson } from '@/lib/police-map/map-style'
import { searchPlaces } from '@/lib/police-map/search'
import type { Address } from '@/lib/types'

function pin(id: string, name: string, count: number, extra: Partial<Address> = {}): Address {
  return {
    id,
    kind: 'place',
    raw_address: name.toUpperCase(),
    normalized_address: name,
    count,
    traffic_count: 0,
    lat: 43.674,
    lng: -72.2656,
    precision: 'exact',
    street_id: null,
    hidden: false,
    ...extra,
  }
}

const STREET = pin('mount-support-rd', 'Mount Support Rd', 600, {
  kind: 'road',
  precision: 'approximate',
})
const QUARRY = pin('quarry-hill', 'Quarry Hill Town Houses, Mount Support Rd', 900, {
  precision: 'approximate',
  street_id: 'mount-support-rd',
  hidden: true,
})
const MAREK = pin('marek', 'Marek, Mount Support Rd', 120, {
  precision: 'approximate',
  street_id: 'mount-support-rd',
  hidden: true,
})
const LONELY = pin('lonely', 'Lonely Shop, 12 Elm St', 50, { precision: 'approximate' })
const FORD = pin('ford', 'Lebanon Ford, Miracle Mile', 400)
const ALL = [FORD, MAREK, STREET, QUARRY, LONELY]
const PLACES = new Map(ALL.map((a) => [a.id, a]))

describe('hidden places on the map', () => {
  it('leave no pin of their own', () => {
    const ids = pinsGeoJson(ALL).features.map((f) => f.properties.id)

    expect(ids).toEqual(['ford', 'mount-support-rd', 'lonely'])
  })

  it('ride on their street pin: its size, and the calls a tooltip or group shows', () => {
    const street = pinsGeoJson(ALL).features.find((f) => f.properties.id === 'mount-support-rd')

    expect(street?.properties.n).toBe(600)
    expect(street?.properties.h).toBe(1020)
    expect(street?.properties.w).toBe(600 + 900 + 120)
  })

  it('flag a kept approximate place for the tooltip, and nothing else', () => {
    const flags = Object.fromEntries(
      pinsGeoJson(ALL).features.map((f) => [f.properties.id, f.properties.a]),
    )

    expect(flags).toEqual({ ford: 0, 'mount-support-rd': 0, lonely: 1 })
  })

  it('leave no calls out of what the pins hold, so a group matches the town total', () => {
    const held = pinsGeoJson(ALL).features.reduce(
      (sum, f) => sum + f.properties.n + f.properties.h,
      0,
    )

    expect(held).toBe(ALL.reduce((sum, a) => sum + a.count, 0))
  })

  it('still count in the totals the caller computes from the whole list', () => {
    expect(ALL.reduce((sum, a) => sum + a.count, 0)).toBe(2070)
    expect(hiddenCallsByStreet(ALL).get('mount-support-rd')).toBe(1020)
  })
})

describe('placesOnStreet', () => {
  it('lists the hidden places on a street, busiest first', () => {
    expect(placesOnStreet(ALL, 'mount-support-rd').map((a) => a.id)).toEqual([
      'quarry-hill',
      'marek',
    ])
  })

  it('lists nothing for a street with none', () => {
    expect(placesOnStreet(ALL, 'elm-st')).toEqual([])
  })

  it('does not reorder the list it is given', () => {
    placesOnStreet(ALL, 'mount-support-rd')
    expect(ALL.map((a) => a.id)).toEqual([
      'ford',
      'marek',
      'mount-support-rd',
      'quarry-hill',
      'lonely',
    ])
  })
})

describe('the street an approximate place is on', () => {
  it('is its street pin, when it has one', () => {
    expect(streetPinOf(QUARRY, PLACES)?.id).toBe('mount-support-rd')
    expect(streetNameOf(QUARRY, PLACES)).toBe('Mount Support Rd')
  })

  it('is the street of its own address, without the house number, when it has none', () => {
    expect(streetPinOf(LONELY, PLACES)).toBeUndefined()
    expect(streetNameOf(LONELY, PLACES)).toBe('Elm St')
  })

  it('is nothing for a place with no street at all', () => {
    expect(streetNameOf(pin('x', 'Mystery', 1), PLACES)).toBeNull()
  })
})

describe('isApproximatePlace', () => {
  it('is for places only, not roads or exact places', () => {
    expect(isApproximatePlace(QUARRY)).toBe(true)
    expect(isApproximatePlace(STREET)).toBe(false)
    expect(isApproximatePlace(FORD)).toBe(false)
  })
})

describe('the copy', () => {
  it('says where an approximate place is', () => {
    expect(approximateLine('Mount Support Rd')).toBe(
      'Approximate location, somewhere on Mount Support Rd',
    )
    expect(approximateLine(null)).toBe('Approximate location')
  })

  it('heads the list on a street card', () => {
    expect(onStreetHeading('Mount Support Rd')).toBe('On Mount Support Rd, exact spot unknown')
  })
})

describe('search', () => {
  it('still finds a hidden place', () => {
    expect(searchPlaces(ALL, 'quarry').map((a) => a.id)).toEqual(['quarry-hill'])
  })
})
