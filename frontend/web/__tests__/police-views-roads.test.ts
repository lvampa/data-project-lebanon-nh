import { describe, expect, it } from 'vitest'
import { decodeActivity } from '@/lib/police-views/activity'
import { cardGroupOf, filteredAddresses, tally } from '@/lib/police-views/counts'
import { DEFAULT_FILTERS, readQuery, withRoadsKind, writeQuery } from '@/lib/police-views/filters'
import { buildRoads, parseCrossing, parseSpot } from '@/lib/police-views/roads'
import { roadKey, routeKey } from '@/lib/police-views/route'
import { selectEntries } from '@/lib/police-views/select'
import type { Address } from '@/lib/types'
import { activityFile, address, type FixtureEntry } from './police-views-fixture'

const idOf = (name: string) => name.toLowerCase().replaceAll(' ', '-')
const road = (name: string, count: number): Address =>
  address(idOf(name), { kind: 'road', normalized_address: name, raw_address: name, count })

function roadsOf(addresses: Address[]) {
  return buildRoads(addresses, new Map())
}
const pick = (roads: ReturnType<typeof roadsOf>['roads'], name: string) =>
  roads.find((r) => r.name === name)!

describe('routeKey', () => {
  it.each([
    ['I-89', 'I 89'],
    ['Interstate 89', 'I 89'],
    ['NH Route 120', 'NH 120'],
    ['Route 120', 'NH 120'],
    ['NH 120', 'NH 120'],
    ['US Route 4', 'US 4'],
    ['U.S. 4', 'US 4'],
  ])('reads %s as %s', (name, key) => {
    expect(routeKey(name)).toBe(key)
  })

  it('reads a bare Route 4 as the federal road when only that one is named', () => {
    expect(routeKey('Route 4', new Set(['US 4']))).toBe('US 4')
    expect(routeKey('Route 4', new Set(['US 4', 'NH 4']))).toBe('NH 4')
    expect(routeKey('Route 4')).toBe('NH 4')
  })

  it('has no key for a street', () => {
    expect(routeKey('Main St')).toBeNull()
    expect(roadKey('Main St')).toBe('main st')
  })
})

describe('parseCrossing', () => {
  it('splits two roads joined by "and"', () => {
    expect(parseCrossing('Heater Rd and NH Route 120')).toEqual(['Heater Rd', 'NH Route 120'])
  })

  it.each(['Main St', 'I-89 at Exits 19 and 20', 'Plainfield Rd and I-89 southbound near Exit 20'])(
    'does not read %s as a crossing by its name',
    (name) => {
      expect(parseCrossing(name)).toBeNull()
    },
  )

  it('keeps a road whose name has "lane" in it', () => {
    expect(parseCrossing('Poverty Lane and Main St')).toEqual(['Poverty Lane', 'Main St'])
  })

  it('keeps a road whose name has "mile" in it', () => {
    expect(parseCrossing('Glen Rd and Miracle Mile')).toEqual(['Glen Rd', 'Miracle Mile'])
  })
})

describe('parseSpot', () => {
  const known = new Set(['mechanic st', 'plainfield rd'])
  const isRoad = (text: string) => known.has(roadKey(text)) || routeKey(text) !== null
  const keyOf = (text: string) => roadKey(text)

  it('reads two roads in one name as a crossing', () => {
    expect(parseSpot('I-89 near Mechanic St', isRoad, keyOf)).toEqual({
      roads: ['I-89', 'Mechanic St'],
      point: null,
    })
    expect(parseSpot('I-89 at NH Route 120 interchange', isRoad, keyOf)?.roads).toEqual([
      'I-89',
      'NH Route 120',
    ])
    expect(
      parseSpot('Plainfield Rd and I-89 southbound near Exit 20', isRoad, keyOf)?.roads,
    ).toEqual(['Plainfield Rd', 'I-89'])
  })

  it('reads one road and an exit as a point on the road', () => {
    expect(parseSpot('I-89 northbound on-ramp at Exit 18', isRoad, keyOf)).toEqual({
      roads: ['I-89'],
      point: 'Exit 18',
    })
  })

  it('does not take a landmark for a road', () => {
    expect(parseSpot('Example Storage near I-89 Exit 16', isRoad, keyOf)).toEqual({
      roads: ['I-89'],
      point: 'Exit 16',
    })
  })

  it('names no road when the text has none', () => {
    expect(parseSpot('Example Walking Bridge over Example Creek', isRoad, keyOf)).toBeNull()
  })
})

describe('buildRoads', () => {
  it('leads a road with its own number and counts its crossings on a line of their own', () => {
    const { roads } = roadsOf([
      road('Alpha Rd', 10),
      road('Beta St', 5),
      road('Alpha Rd and Beta St', 7),
    ])

    const alpha = pick(roads, 'Alpha Rd')
    expect([alpha.headline, alpha.atCrossings, alpha.hasOwnPin]).toEqual([10, 7, true])
    expect(pick(roads, 'Beta St').headline).toBe(5)
  })

  it('counts a crossing on both of its roads', () => {
    const { roads, crossings } = roadsOf([road('Alpha Rd and Beta St', 7)])

    expect(roads.map((r) => [r.name, r.headline, r.atCrossings])).toEqual([
      ['Alpha Rd', 7, 7],
      ['Beta St', 7, 7],
    ])
    expect(crossings.map((c) => [c.name, c.n])).toEqual([['Alpha Rd and Beta St', 7]])
  })

  it("adds the places listed on a road to the road's number, as the map does", () => {
    const listed = address('example-market', {
      count: 4,
      street_id: 'alpha-rd',
      hidden: true,
    })

    const { roads } = roadsOf([road('Alpha Rd', 10), listed])

    expect(roads.map((r) => [r.name, r.headline])).toEqual([['Alpha Rd', 14]])
  })

  it('gives a road with no pin of its own a card, led by its crossings and shown on the busiest', () => {
    const { roads } = roadsOf([road('Side St and Alpha Rd', 4), road('Other Ln and Side St', 9)])

    const side = pick(roads, 'Side St')
    expect([side.headline, side.hasOwnPin, side.atCrossings]).toEqual([13, false, 13])
    expect(side.showId).toBe('other-ln-and-side-st')
  })

  it('shows a road with its own pin on that pin', () => {
    const { roads } = roadsOf([road('Alpha Rd', 1), road('Alpha Rd and Beta St', 7)])

    expect(pick(roads, 'Alpha Rd').showId).toBe('alpha-rd')
  })

  it('lists the crossings busiest first, with ties by the other road', () => {
    const { roads } = roadsOf([
      road('Main St', 1),
      road('Main St and Zed Ave', 20),
      road('Birch Ln and Main St', 11),
      road('Main St and Oak Ln', 11),
      road('Main St and Pine Ct', 3),
    ])

    expect(pick(roads, 'Main St').crossings.map((c) => [c.other, c.n])).toEqual([
      ['Zed Ave', 20],
      ['Birch Ln', 11],
      ['Oak Ln', 11],
      ['Pine Ct', 3],
    ])
  })

  it('sorts roads by the number they lead with', () => {
    const { roads } = roadsOf([
      road('Small St', 3),
      road('Big St', 30),
      road('Alpha Rd and Small St', 50),
    ])

    expect(roads.map((r) => r.name)).toEqual(['Alpha Rd', 'Big St', 'Small St'])
  })

  it('leaves out a pin with no entries', () => {
    const { roads, crossings } = roadsOf([
      road('Alpha Rd', 0),
      road('Beta St', 5),
      road('Alpha Rd and Beta St', 0),
    ])

    expect(roads.map((r) => r.name)).toEqual(['Beta St'])
    expect(crossings).toEqual([])
  })

  it('adds the weeks of the pins a road leads with', () => {
    const addresses = [road('Alpha Rd', 3), road('Beta St and Gamma Ln', 2)]

    const { crossings } = buildRoads(
      addresses,
      new Map([
        [0, [1, 2, 0]],
        [1, [0, 1, 1]],
      ]),
    )

    expect(crossings[0].weeks).toEqual([0, 1, 1])
  })

  it('joins spellings of one route, so a crossing with Route 120 is a crossing with NH Route 120', () => {
    const { roads } = roadsOf([
      road('NH Route 120', 149),
      road('Heater Rd and NH Route 120', 114),
      road('Alta Blvd and Route 120', 79),
    ])

    const route = pick(roads, 'NH Route 120')
    expect([route.headline, route.atCrossings]).toEqual([149, 193])
    expect(roads.filter((r) => routeKey(r.name) === 'NH 120')).toHaveLength(1)
  })

  describe('a pin named for a spot', () => {
    it('counts toward both roads when it names two', () => {
      const { roads, crossings } = roadsOf([
        road('I-89', 5),
        road('Mechanic St', 20),
        road('I-89 near Mechanic St', 66),
      ])

      expect(pick(roads, 'I-89').atCrossings).toBe(66)
      expect(pick(roads, 'Mechanic St').atCrossings).toBe(66)
      expect(crossings.map((c) => [c.name, c.n])).toEqual([['I-89 and Mechanic St', 66]])
    })

    it('counts a highway and a route by its number, however it is spelled', () => {
      const { roads } = roadsOf([
        road('Interstate 89', 5),
        road('Route 120', 149),
        road('I-89 at NH Route 120 interchange', 46),
      ])

      expect(pick(roads, 'Interstate 89').atCrossings).toBe(46)
      expect(pick(roads, 'Route 120').atCrossings).toBe(46)
      expect(roads).toHaveLength(2)
    })

    it('counts toward the one road it names, as a point on it, when it gives an exit', () => {
      const { roads, crossings } = roadsOf([
        road('I-89', 5),
        road('I-89 southbound near Exit 17', 14),
        road('I-89 northbound on-ramp at Exit 17', 3),
      ])

      const interstate = pick(roads, 'I-89')
      expect(interstate.headline).toBe(5)
      expect(interstate.crossings).toEqual([
        { id: 'i-89-southbound-near-exit-17', other: 'Exit 17', n: 17 },
      ])
      expect(roads).toHaveLength(1)
      expect(crossings).toEqual([])
    })

    it('counts the spellings of one crossing as one, on the busiest pin', () => {
      const { crossings } = roadsOf([
        road('Plainfield Rd and I-89', 6),
        road('Plainfield Rd and I-89 near Exit 20', 2),
      ])

      expect(crossings).toHaveLength(1)
      expect([crossings[0].n, crossings[0].id]).toEqual([8, 'plainfield-rd-and-i-89'])
    })

    it('counts a crossing of a road named Lane, and a left lane on a highway as the highway', () => {
      const { roads } = roadsOf([
        road('Main St', 4),
        road('Poverty Lane and Main St', 9),
        road('I-89', 1),
        road('I-89 southbound left lane near Exit 17', 3),
      ])

      expect(pick(roads, 'Main St').crossings).toEqual([
        { id: 'poverty-lane-and-main-st', other: 'Poverty Lane', n: 9 },
      ])
      expect(pick(roads, 'I-89').atCrossings).toBe(3)
    })

    it('joins a bare Route 4 to US Route 4', () => {
      const { roads } = roadsOf([
        road('US Route 4', 10),
        road('Route 4', 5),
        road('Oak St and Route 4', 2),
      ])

      const route = roads.filter((r) => routeKey(r.name, new Set(['US 4'])) === 'US 4')
      expect(route).toHaveLength(1)
      expect([route[0].headline, route[0].atCrossings]).toEqual([15, 2])
    })

    it('keeps a name with no road in it as a road of its own', () => {
      const { roads } = roadsOf([road('Example Walking Bridge over Example Creek', 2)])

      expect(roads.map((r) => r.name)).toEqual(['Example Walking Bridge over Example Creek'])
    })
  })
})

describe('road counts under the filters', () => {
  const ADDRESSES = [road('Alpha Rd', 0), road('Alpha Rd and Beta St', 0)]
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
    const shown = filteredAddresses(ADDRESSES, activity, kept)
    const cards = tally(activity, kept, cardGroupOf(activity, shown))
    const { roads } = buildRoads(shown, new Map([...cards].map(([pin, t]) => [pin, t.weeks])))
    return roads.map((r) => [r.name, r.headline, r.atCrossings])
  }

  it('counts every entry with no filter', () => {
    expect(totals({})).toEqual([
      ['Alpha Rd', 2, 1],
      ['Beta St', 1, 1],
    ])
  })

  it('counts only the entries the filters keep', () => {
    expect(totals({ time: 'night' })).toEqual([
      ['Alpha Rd', 1, 1],
      ['Beta St', 1, 1],
    ])
    expect(totals({ time: 'day' })).toEqual([['Alpha Rd', 1, 0]])
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

describe('the kind on the Roads tab', () => {
  it('rewrites the kind only for the Roads view, so Places keeps the one in the link', () => {
    const filters = { ...DEFAULT_FILTERS, kind: 'alarms' as const }

    expect(withRoadsKind('roads', filters).kind).toBe('all')
    expect(withRoadsKind('places', filters).kind).toBe('alarms')
  })

  it.each(['place', 'alarms'] as const)('opens a link with kind %s on all activity', (kind) => {
    expect(withRoadsKind('roads', { ...DEFAULT_FILTERS, kind }).kind).toBe('all')
  })

  it('keeps all activity and traffic, and leaves the other tabs alone', () => {
    expect(withRoadsKind('roads', { ...DEFAULT_FILTERS, kind: 'traffic' }).kind).toBe('traffic')
    expect(withRoadsKind('places', { ...DEFAULT_FILTERS, kind: 'alarms' }).kind).toBe('alarms')
  })
})
