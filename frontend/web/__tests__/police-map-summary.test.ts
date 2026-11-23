import { describe, expect, it } from 'vitest'
import { resultCount, searchPlaces } from '@/lib/police-map/search'
import {
  busiestDay,
  busiestHour,
  busiestPlaces,
  busiestStreets,
  hourLabel,
  mappedTotal,
} from '@/lib/police-map/summary'
import type { Address } from '@/lib/types'

function place(id: string, name: string, count: number): Address {
  return {
    id,
    kind: 'place',
    raw_address: name.toUpperCase(),
    normalized_address: name,
    count,
    traffic_count: 0,
    lat: 43.64,
    lng: -72.25,
    precision: 'exact',
    street_id: null,
    hidden: false,
  }
}

const PLACES = [
  place('a', 'Lebanon Ford, 90 Miracle Mile', 400),
  place('b', 'Walmart, 45 Glen Rd', 1200),
  place('c', 'Miracle Mile', 900),
  place('d', 'Kmart, 12 Miracle Mile', 40),
]

describe('hourLabel', () => {
  it('names midnight, noon and the rest on a 12 hour clock', () => {
    expect([0, 1, 11, 12, 13, 23].map(hourLabel)).toEqual([
      '12 am',
      '1 am',
      '11 am',
      'noon',
      '1 pm',
      '11 pm',
    ])
  })
})

describe('busiestDay and busiestHour', () => {
  it('pick the day and the hour with the most calls', () => {
    expect(
      busiestDay([
        { day: 'Thu', count: 20 },
        { day: 'Fri', count: 40 },
      ]),
    ).toBe('Friday')
    expect(
      busiestHour([
        { hour: 3, count: 5 },
        { hour: 16, count: 30 },
      ]),
    ).toBe('4 pm')
  })

  it('say nothing with no data', () => {
    expect(busiestDay([])).toBeNull()
    expect(busiestHour([])).toBeNull()
  })
})

describe('busiestPlaces', () => {
  it('lists the places with the most calls first, up to the limit', () => {
    expect(busiestPlaces(PLACES, 2).map((p) => p.id)).toEqual(['b', 'c'])
  })

  it('does not reorder the list it is given', () => {
    busiestPlaces(PLACES, 2)
    expect(PLACES.map((p) => p.id)).toEqual(['a', 'b', 'c', 'd'])
  })
})

describe('the two busiest lists', () => {
  const street = { ...place('s', 'Main St', 400), kind: 'road' as const }
  const crossing = { ...place('x', 'Main St and Elm St', 900), kind: 'road' as const }
  const hidden = { ...place('h', 'Bank, Main St', 300), street_id: 's', hidden: true }
  const shop = { ...place('p', 'Shop, 2 Elm St', 500), traffic_count: 40 }
  const pins = [street, crossing, hidden, shop]

  // Its order must match the places' rank lines, which count every place.
  it('lists every place, including one listed on its street, and no streets', () => {
    expect(busiestPlaces(pins, 5).map((p) => p.id)).toEqual(['p', 'h'])
  })

  it('lists streets on their totals, with the places on them, and no crossings', () => {
    expect(busiestStreets(pins, 5)).toEqual([{ address: street, total: 700 }])
  })

  it('counts every entry on the map once: roads, places, and traffic at places', () => {
    expect(mappedTotal(pins)).toBe(400 + 900 + 300 + 500 + 40)
  })
})

describe('a traffic-only place in search', () => {
  const corner = { ...place('t', 'Corner Shop, Glen Rd', 0), traffic_count: 62 }

  it('shows its traffic count with a label', () => {
    expect(resultCount(corner, new Map())).toBe('62 traffic')
    expect(resultCount(place('a', 'Mall', 1200), new Map())).toBe('1,200')
  })

  it('sorts by that count', () => {
    const found = searchPlaces([place('p', 'Glen Rd Shop', 10), corner], 'glen')
    expect(found.map((p) => p.id)).toEqual(['t', 'p'])
  })
})

describe('searchPlaces', () => {
  it('matches a name in any case, busiest first', () => {
    expect(searchPlaces(PLACES, 'miracle').map((p) => p.id)).toEqual(['c', 'a', 'd'])
  })

  it('waits for two letters', () => {
    expect(searchPlaces(PLACES, 'm')).toEqual([])
    expect(searchPlaces(PLACES, '  ')).toEqual([])
  })

  it('stops at the limit', () => {
    expect(searchPlaces(PLACES, 'mile', 2)).toHaveLength(2)
  })

  it('matches a street typed short or spelled out', () => {
    const street = place('m', 'Mount Support Rd', 10)
    const ids = (query: string) => searchPlaces([street], query).map((p) => p.id)
    expect(ids('mt support')).toEqual(['m'])
    expect(ids('Mt. Support')).toEqual(['m'])
    expect(ids('mount support road')).toEqual(['m'])
  })

  it('matches a direction typed short or spelled out', () => {
    const street = place('n', 'N Main St', 10)
    expect(searchPlaces([street], 'north main').map((p) => p.id)).toEqual(['n'])
  })

  it('finds a direction typed alone, only where a word starts', () => {
    const places = [place('w', 'W Lebanon Plaza', 10), place('h', 'Hawthorne St', 5)]
    expect(searchPlaces(places, 'west').map((p) => p.id)).toEqual(['w'])
  })

  it('matches a shortened word only as a whole word', () => {
    const places = [place('s', 'S Main St', 10), place('t', 'Support St', 5)]
    expect(searchPlaces(places, 'south').map((p) => p.id)).toEqual(['s'])
  })

  it('reads nothing off the prototype for a word like constructor', () => {
    expect(searchPlaces([place('c', 'Main St', 10)], 'constructor')).toEqual([])
  })

  it('still matches inside a word as typed', () => {
    expect(searchPlaces([place('h', 'Hannaford', 10)], 'anna').map((p) => p.id)).toEqual(['h'])
  })

  it('matches past the punctuation in a name', () => {
    expect(
      searchPlaces([place('q', 'Quarry Hill, Mount Support Rd', 10)], 'hill mt').map((p) => p.id),
    ).toEqual(['q'])
  })
})
