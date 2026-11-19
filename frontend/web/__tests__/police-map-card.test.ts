import { describe, expect, it } from 'vitest'
import { categoriesFor } from '@/lib/police-map/categories'
import { formatCallTime } from '@/lib/police-map/format'
import { rankLine } from '@/lib/police-map/rank'
import { osmStreetNames, streetsToLight } from '@/lib/police-map/streets'

describe('rankLine', () => {
  const counts = [100, 80, 60, 40, 20, 10, 5, 4, 3, 1]

  it('says how many places have fewer calls, and the place in line', () => {
    expect(rankLine(100, counts)).toBe('More calls than 90% of places in Lebanon · #1 of 10')
    expect(rankLine(40, counts)).toBe('More calls than 60% of places in Lebanon · #4 of 10')
  })

  it('does not boast when the place is in the lower half', () => {
    expect(rankLine(3, counts)).toBe('Fewer calls than most places in Lebanon')
  })

  it('shares a rank in a tie, and counts only the places below it as passed', () => {
    expect(rankLine(5, [5, 5, 1, 1])).toBe('More calls than 50% of places in Lebanon · #1 of 4')
    expect(rankLine(5, [5, 5, 5, 1])).toBe('Fewer calls than most places in Lebanon')
  })

  it('says nothing with no places to compare with', () => {
    expect(rankLine(5, [])).toBe('')
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
