import { describe, expect, it } from 'vitest'
import { categoriesFor } from '@/lib/police-map/categories'
import { formatCallTime } from '@/lib/police-map/format'
import { remainder } from '@/lib/police-map/card'
import { ordinal, rankLine } from '@/lib/police-map/rank'
import { osmStreetNames, streetsToLight } from '@/lib/police-map/streets'

describe('ordinal', () => {
  it('spells the ordinals, including the teens', () => {
    expect([1, 2, 3, 4, 11, 12, 13, 21, 22, 101, 111].map(ordinal)).toEqual([
      '1st',
      '2nd',
      '3rd',
      '4th',
      '11th',
      '12th',
      '13th',
      '21st',
      '22nd',
      '101st',
      '111th',
    ])
  })
})

describe('rankLine', () => {
  const counts = [100, 80, 60, 40, 20, 10, 5, 4, 3, 1]

  it('gives the place in line out of the pins of its kind', () => {
    expect(rankLine(100, counts, 'place')).toBe('1st busiest of 10 places in Lebanon')
    expect(rankLine(40, counts, 'place')).toBe('4th busiest of 10 places in Lebanon')
  })

  it('does not boast when the place is in the lower half', () => {
    expect(rankLine(3, counts, 'place')).toBe('Quieter than most places in Lebanon')
  })

  it('shares a rank in a tie, and counts only the places below it as passed', () => {
    expect(rankLine(5, [5, 5, 1, 1], 'place')).toBe('1st busiest of 4 places in Lebanon')
    expect(rankLine(5, [5, 5, 5, 1], 'place')).toBe('Quieter than most places in Lebanon')
  })

  it('ranks a street against streets and says so', () => {
    expect(rankLine(9, [9, 5, 1], 'road')).toBe('1st busiest of 3 streets in Lebanon')
    expect(rankLine(1, [9, 5, 1], 'road')).toBe('Quieter than most streets in Lebanon')
  })

  it('puts thousands in the total', () => {
    expect(rankLine(2, [...Array.from({ length: 1289 }, () => 1), 2], 'place')).toBe(
      '1st busiest of 1,290 places in Lebanon',
    )
  })

  it('says nothing with no pins to compare with', () => {
    expect(rankLine(5, [], 'place')).toBe('')
  })
})

describe('remainder', () => {
  it('is what the rows leave out of the total', () => {
    expect(
      remainder(
        [
          ['A', 5],
          ['B', 3],
        ],
        10,
      ),
    ).toBe(2)
  })

  it('is never negative', () => {
    expect(remainder([['A', 5]], 3)).toBe(0)
  })
})

describe('osmStreetNames', () => {
  it('spells out the suffix and the direction, as the map tiles do', () => {
    expect(osmStreetNames('Lebanon Ford, 90 N Main St')).toEqual(['North Main Street'])
    expect(osmStreetNames('Mall, 1 Glen Rd')).toEqual(['Glen Road'])
  })

  it('takes a road by its own name', () => {
    expect(osmStreetNames('Miracle Mile')).toEqual(['Miracle Mile'])
  })

  it('lights both streets of an intersection', () => {
    expect(osmStreetNames('Main St and Hanover St')).toEqual(['Main Street', 'Hanover Street'])
  })

  it('drops a house number, a unit letter and a parenthesis', () => {
    expect(osmStreetNames('Shop, 12A Elm Ave (rear)')).toEqual(['Elm Avenue'])
  })
})

describe('streetsToLight', () => {
  const place = {
    kind: 'place' as const,
    traffic_count: 0,
    normalized_address: 'Lebanon Ford, 90 Miracle Mile',
    raw_address: 'LEBANON FORD',
  }

  it('lights nothing for a place with no traffic', () => {
    expect(streetsToLight(place)).toEqual([])
  })

  it('lights the street of a place that has traffic on it', () => {
    expect(streetsToLight({ ...place, traffic_count: 4 })).toEqual(['Miracle Mile'])
  })

  it('lights a road', () => {
    expect(streetsToLight({ ...place, kind: 'road', normalized_address: 'Miracle Mile' })).toEqual([
      'Miracle Mile',
    ])
  })
})

describe('categoriesFor', () => {
  const counts = { premises: 5, traffic: 3, alarms: 0, checks: 2, admin: 0 }

  it('leaves traffic out for a place, and keeps the order', () => {
    expect(categoriesFor('place', counts).map((c) => c.key)).toEqual(['premises', 'checks'])
  })

  it('keeps traffic for a road', () => {
    expect(categoriesFor('road', counts).map((c) => c.key)).toEqual([
      'premises',
      'traffic',
      'checks',
    ])
  })
})

describe('formatCallTime', () => {
  it('reads the log time as it is, with no zone shift', () => {
    expect(formatCallTime('2026-11-18T14:05:00')).toBe('Nov 18, 2:05 pm')
    expect(formatCallTime('2026-03-02T00:30:00')).toBe('Mar 2, 12:30 am')
    expect(formatCallTime('2026-03-02T12:00:00')).toBe('Mar 2, 12:00 pm')
  })

  it('says so when a call has no time', () => {
    expect(formatCallTime(null)).toBe('Time not recorded')
  })
})
