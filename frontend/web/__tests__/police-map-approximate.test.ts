import { describe, expect, it } from 'vitest'
import {
  hiddenCallsByStreet,
  isApproximatePlace,
  placesOnStreet,
  rankCounts,
  streetNameOf,
  streetPinOf,
  streetTotal,
} from '@/lib/police-map/approximate'
import {
  alarmsLine,
  approximateLine,
  clusterHolds,
  entryWord,
  whoStartedLine,
  onStreetHeading,
  streetBreakdown,
  streetItselfLine,
} from '@/lib/police-map/format'
import { pinsGeoJson } from '@/lib/police-map/map-style'
import { resultCount, searchPlaces } from '@/lib/police-map/search'
import type { Address } from '@/lib/types'

function pin(id: string, name: string, count: number, extra: Partial<Address> = {}): Address {
  return {
    id,
    kind: 'place',
    raw_address: name.toUpperCase(),
    normalized_address: name,
    count,
    traffic_count: 0,
    nearby_traffic: 0,
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

describe("a street's total", () => {
  // The pin you click and the card you read must show the same number.
  it('is the street plus the places listed on it, as the tooltip counts', () => {
    const onStreet = placesOnStreet(ALL, 'mount-support-rd')
    const tooltip = pinsGeoJson(ALL).features.find((f) => f.properties.id === 'mount-support-rd')

    expect(streetTotal(STREET, onStreet)).toBe(1620)
    expect(streetTotal(STREET, onStreet)).toBe(
      (tooltip?.properties.n ?? 0) + (tooltip?.properties.h ?? 0),
    )
  })

  it('is just its own count for a place', () => {
    expect(streetTotal(FORD, [])).toBe(400)
  })

  it('ranks streets on their totals, and places on their own counts', () => {
    expect(rankCounts(ALL, 'road')).toEqual([1620])
    expect(rankCounts(ALL, 'place').sort((a, b) => a - b)).toEqual([50, 120, 400, 900])
  })

  it('is what search shows and sorts by, so a street ranks above its own places', () => {
    const found = searchPlaces(ALL, 'mount support')

    expect(found.map((a) => a.id)).toEqual(['mount-support-rd', 'quarry-hill', 'marek'])
    expect(resultCount(found[0], hiddenCallsByStreet(ALL))).toBe('1,620')
  })

  it('names a count with the filter in use, like the count line and the card', () => {
    expect(entryWord(54, 'traffic stops and calls')).toBe('54 traffic stops and calls')
    expect(entryWord(1, 'traffic stops and calls')).toBe('1 traffic stop or call')
    expect(entryWord(1)).toBe('1 log entry')
    expect(entryWord(2, 'alarms')).toBe('2 alarms')
  })

  it("counts a group's traffic when the filter is traffic, and its calls otherwise", () => {
    expect(clusterHolds(0, 300, 'traffic stops and calls')).toBe('300 traffic stops and calls')
    expect(clusterHolds(120, 300, 'traffic stops and calls')).toBe('300 traffic stops and calls')
    expect(clusterHolds(120, 300)).toBe('120 log entries')
  })

  // Both counted: "the rest were started by officers" was false at the station and on streets.
  it('says how many of a filtered count came from the public and from officers', () => {
    expect(whoStartedLine(202, 399)).toBe(
      '202 were calls from the public and 399 were started by officers.',
    )
    expect(whoStartedLine(1, 1)).toBe('1 was a call from the public and 1 was started by officers.')
  })

  it('says a Places card leaves out all of its alarms, not only the false ones', () => {
    expect(alarmsLine(3, 1)).toBe('3 alarms, 1 false, not counted above')
    expect(alarmsLine(1, 0)).toBe('1 alarm, not counted above')
  })

  it("says a street card's lists cover the street itself", () => {
    expect(streetItselfLine(409)).toBe(
      'These lists cover the street itself, the whole year: 409 entries.',
    )
  })

  it('says where the total comes from', () => {
    expect(streetBreakdown(600, placesOnStreet(ALL, 'mount-support-rd'))).toBe(
      '600 at the street itself · 1,020 at 2 places on it',
    )
    expect(streetBreakdown(600, [MAREK])).toBe('600 at the street itself · 120 at 1 place on it')
  })
})

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

  // A "0" row reads as an error, and its card then says "10 traffic stops nearby".
  it('leaves out a place with no entries of its own, such as one with only traffic', () => {
    const trafficOnly = pin('lot', 'Parking Lot, Mount Support Rd', 0, {
      traffic_count: 10,
      street_id: 'mount-support-rd',
      hidden: true,
    })
    expect(placesOnStreet([...ALL, trafficOnly], 'mount-support-rd').map((a) => a.id)).toEqual([
      'quarry-hill',
      'marek',
    ])
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
