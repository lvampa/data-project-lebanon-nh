import { describe, expect, it } from 'vitest'
import { searchPlaces } from '@/lib/police-map/search'
import { busiestDay, busiestHour, busiestPlaces, hourLabel } from '@/lib/police-map/summary'
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
})
