import { describe, expect, it } from 'vitest'
import { decodeActivity } from '@/lib/police-views/activity'
import { tally } from '@/lib/police-views/counts'
import { DEFAULT_FILTERS, readQuery, writeQuery } from '@/lib/police-views/filters'
import { buildRoads, parseCrossing, type PinCount } from '@/lib/police-views/roads'
import { selectEntries } from '@/lib/police-views/select'
import type { Address } from '@/lib/types'
import { activityFile, address, type FixtureEntry } from './police-views-fixture'

const road = (name: string, id = name.toLowerCase().replaceAll(' ', '-')): Address =>
  address(id, { kind: 'road', normalized_address: name, raw_address: name })

const countOf = (n: number): PinCount => ({ n, weeks: [n] })

function counts(addresses: Address[], byId: Record<string, number>): Map<number, PinCount> {
  return new Map(
    addresses.flatMap((a, i) => (a.id in byId ? [[i, countOf(byId[a.id])] as const] : [])),
  )
}

describe('parseCrossing', () => {
  it('splits two roads joined by "and"', () => {
    expect(parseCrossing('Heater Rd and NH Route 120')).toEqual(['Heater Rd', 'NH Route 120'])
  })

  it.each([
    'Main St',
    'I-89 at Exits 19 and 20',
    'I-89 northbound between Exit 19 and Exit 20',
    'Plainfield Rd and I-89 southbound near Exit 20',
    'A and B and C',
  ])('leaves %s as a road of its own', (name) => {
    expect(parseCrossing(name)).toBeNull()
  })

  it('keeps a road whose name has "mile" in it', () => {
    expect(parseCrossing('Glen Rd and Miracle Mile')).toEqual(['Glen Rd', 'Miracle Mile'])
  })
})

describe('buildRoads', () => {
  const ADDRESSES = [
    road('Alpha Rd'),
    road('Beta St'),
    road('Alpha Rd and Beta St'),
    // A place listed on Alpha Rd stays on the Places tab.
    address('example-market', { street_id: 'alpha-rd', hidden: true }),
  ]

  it("adds a road's own pin to every crossing it is part of", () => {
    const { roads } = buildRoads(
      ADDRESSES,
      counts(ADDRESSES, { 'alpha-rd': 10, 'beta-st': 5, 'alpha-rd-and-beta-st': 7 }),
    )

    const alpha = roads.find((r) => r.name === 'Alpha Rd')!
    const beta = roads.find((r) => r.name === 'Beta St')!
    // The crossing counts toward both roads, so the two add up to more than the pins hold.
    expect([alpha.own, alpha.atCrossings, alpha.total]).toEqual([10, 7, 17])
    expect([beta.own, beta.atCrossings, beta.total]).toEqual([5, 7, 12])
  })

  it('leaves out the places listed on a road', () => {
    const { roads } = buildRoads(
      ADDRESSES,
      counts(ADDRESSES, { 'alpha-rd': 10, 'example-market': 99 }),
    )

    expect(roads.map((r) => [r.name, r.total])).toEqual([['Alpha Rd', 10]])
  })

  it('gives a road that appears only in crossings a card, shown on its busiest crossing', () => {
    const addresses = [road('Alpha Rd'), road('Side St and Alpha Rd'), road('Other Ln and Side St')]
    const { roads } = buildRoads(
      addresses,
      counts(addresses, { 'side-st-and-alpha-rd': 4, 'other-ln-and-side-st': 9 }),
    )

    const side = roads.find((r) => r.name === 'Side St')!
    expect([side.own, side.atCrossings, side.total]).toEqual([0, 13, 13])
    expect(side.showId).toBe('other-ln-and-side-st')
  })

  it('shows a road with its own pin on that pin', () => {
    const { roads } = buildRoads(
      ADDRESSES,
      counts(ADDRESSES, { 'alpha-rd': 1, 'alpha-rd-and-beta-st': 7 }),
    )

    expect(roads.find((r) => r.name === 'Alpha Rd')!.showId).toBe('alpha-rd')
  })

  it('lists the top crossings busiest first, with ties by the other road name', () => {
    const addresses = [
      road('Main St'),
      road('Main St and Zed Ave'),
      road('Birch Ln and Main St'),
      road('Main St and Oak Ln'),
      road('Main St and Pine Ct'),
    ]
    const { roads } = buildRoads(
      addresses,
      counts(addresses, {
        'main-st': 1,
        'main-st-and-zed-ave': 20,
        'birch-ln-and-main-st': 11,
        'main-st-and-oak-ln': 11,
        'main-st-and-pine-ct': 3,
      }),
    )

    const main = roads.find((r) => r.name === 'Main St')!
    expect(main.crossings.map((c) => [c.other, c.n])).toEqual([
      ['Zed Ave', 20],
      ['Birch Ln', 11],
      ['Oak Ln', 11],
      ['Pine Ct', 3],
    ])
    expect(main.total).toBe(1 + 20 + 11 + 11 + 3)
  })

  it('leaves out a pin with no entries, and sorts roads busiest first', () => {
    const { roads, crossings } = buildRoads(
      ADDRESSES,
      counts(ADDRESSES, { 'alpha-rd': 0, 'beta-st': 5, 'alpha-rd-and-beta-st': 0 }),
    )

    expect(roads.map((r) => r.name)).toEqual(['Beta St'])
    expect(crossings).toEqual([])
  })

  it('sorts crossings busiest first', () => {
    const addresses = [road('A and B'), road('C and D')]
    const { crossings } = buildRoads(addresses, counts(addresses, { 'a-and-b': 2, 'c-and-d': 6 }))

    expect(crossings.map((c) => c.name)).toEqual(['C and D', 'A and B'])
  })

  it('adds the weekly counts of a road and its crossings', () => {
    const addresses = [road('Alpha Rd'), road('Alpha Rd and Beta St')]
    const { roads } = buildRoads(
      addresses,
      new Map([
        [0, { n: 3, weeks: [1, 2, 0] }],
        [1, { n: 2, weeks: [0, 1, 1] }],
      ]),
    )

    expect(roads.find((r) => r.name === 'Alpha Rd')!.weeks).toEqual([1, 3, 1])
  })
})

describe('filtered road counts', () => {
  const ADDRESSES = [road('Alpha Rd'), road('Alpha Rd and Beta St')]
  const entries: FixtureEntry[] = [
    { pin: 'alpha-rd', day: 1, hour: 10 },
    { pin: 'alpha-rd', day: 1, hour: 22 },
    { pin: 'alpha-rd-and-beta-st', day: 2, hour: 23 },
  ]

  function totals(filters: Partial<typeof DEFAULT_FILTERS>) {
    const activity = decodeActivity(
      activityFile(
        ADDRESSES.map((a) => a.id),
        entries,
      ),
      ADDRESSES,
    )
    const kept = selectEntries(activity, ADDRESSES, { ...DEFAULT_FILTERS, ...filters }, 'all')
    const { roads } = buildRoads(
      ADDRESSES,
      tally(activity, kept, (i) => activity.pin[i]),
    )
    return roads.map((r) => [r.name, r.own, r.atCrossings, r.total])
  }

  it('counts every entry with no filter', () => {
    expect(totals({})).toEqual([
      ['Alpha Rd', 2, 1, 3],
      ['Beta St', 0, 1, 1],
    ])
  })

  it('counts only the entries the filters keep', () => {
    expect(totals({ time: 'night' })).toEqual([
      ['Alpha Rd', 1, 1, 2],
      ['Beta St', 0, 1, 1],
    ])
    expect(totals({ time: 'day' })).toEqual([['Alpha Rd', 1, 0, 1]])
  })
})

describe('the roads URL', () => {
  it('carries the view, and the crossings mode only on that view', () => {
    expect(writeQuery('roads', DEFAULT_FILTERS, 'roads')).toBe('?view=roads')
    expect(writeQuery('roads', DEFAULT_FILTERS, 'crossings')).toBe('?view=roads&mode=crossings')
    expect(writeQuery('places', DEFAULT_FILTERS, 'crossings')).toBe('?view=places')
  })

  it('reads the same view and mode back', () => {
    const query = writeQuery('roads', { ...DEFAULT_FILTERS, time: 'night' }, 'crossings')

    expect(readQuery(query)).toEqual({
      view: 'roads',
      filters: { ...DEFAULT_FILTERS, time: 'night' },
      mode: 'crossings',
    })
  })

  it('falls back to roads for a mode it does not know', () => {
    expect(readQuery('?view=roads&mode=bridges').mode).toBe('roads')
  })
})
