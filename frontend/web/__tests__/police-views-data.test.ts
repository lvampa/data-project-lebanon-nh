import { describe, expect, it } from 'vitest'
import { decodeActivity } from '@/lib/police-views/activity'
import {
  cardGroupOf,
  filteredAddresses,
  tally,
  typical,
  wholeTown,
  TOWN,
} from '@/lib/police-views/counts'
import {
  DEFAULT_FILTERS,
  inTimeOfDay,
  rangeLabel,
  readQuery,
  sheetFilterCount,
  writeQuery,
  type Filters,
} from '@/lib/police-views/filters'
import { STATION_ID, lastDayOf, selectEntries } from '@/lib/police-views/select'
import { SINCE, activityFile, address, times, type FixtureEntry } from './police-views-fixture'

const FORD = address('ford')
const MAIN = address('main-st', { kind: 'road' })
const STATION = address(STATION_ID)
const ADDRESSES = [FORD, MAIN, STATION]

function decode(entries: FixtureEntry[]) {
  return decodeActivity(
    activityFile(
      ADDRESSES.map((a) => a.id),
      entries,
    ),
    ADDRESSES,
  )
}

function kept(entries: FixtureEntry[], filters: Partial<Filters>, lens: 'all' | 'public' = 'all') {
  const activity = decode(entries)
  return Array.from(selectEntries(activity, ADDRESSES, { ...DEFAULT_FILTERS, ...filters }, lens))
}

describe('decodeActivity', () => {
  it('works out the day, week, hour and weekday from minutes after since', () => {
    // Day 0 is Thursday, January 1. Day 8 is the Friday of the second week.
    const activity = decode([
      { pin: 'ford', day: 0, hour: 0 },
      { pin: 'ford', day: 8, hour: 23 },
    ])
    expect(Array.from(activity.day)).toEqual([0, 8])
    expect(Array.from(activity.week)).toEqual([0, 1])
    expect(Array.from(activity.hour)).toEqual([0, 23])
    expect(Array.from(activity.weekday)).toEqual([4, 5])
  })

  it('maps pins to the page addresses by id, and drops a pin the page does not have', () => {
    const file = activityFile(
      ['gone', 'main-st'],
      [
        { pin: 'gone', day: 0 },
        { pin: 'main-st', day: 0 },
      ],
    )
    const activity = decodeActivity(file, ADDRESSES)
    expect(activity.size).toBe(1)
    expect(Array.from(activity.pin)).toEqual([1])
  })
})

describe('the URL query', () => {
  it('is empty for the map with the default filters', () => {
    expect(writeQuery('map', DEFAULT_FILTERS, 'roads')).toBe('')
  })

  it('carries the view and every changed filter, and reads back the same', () => {
    const filters: Filters = { kind: 'traffic', time: 'night', range: '30', officer: 'C. Day' }
    const query = writeQuery('busy', filters, 'roads')
    expect(query).toBe('?view=busy&kind=traffic&time=night&range=30&officer=C.+Day')
    expect(readQuery(query)).toEqual({ view: 'busy', filters, mode: 'roads' })
  })

  it('falls back to the default for a value it does not know', () => {
    expect(readQuery('?view=charts&kind=fire&time=dusk&range=7')).toEqual({
      view: 'map',
      filters: DEFAULT_FILTERS,
      mode: 'roads',
    })
  })

  it('counts the filters behind the phone Filters button, leaving out the kind', () => {
    expect(sheetFilterCount({ ...DEFAULT_FILTERS, kind: 'traffic' })).toBe(0)
    expect(sheetFilterCount({ ...DEFAULT_FILTERS, time: 'day', officer: 'C. Day' })).toBe(2)
  })
})

describe('inTimeOfDay', () => {
  it.each([
    ['day', 6, false],
    ['day', 7, true],
    ['day', 18, true],
    ['day', 19, false],
    ['night', 19, true],
    ['night', 6, true],
    ['night', 7, false],
    ['overnight', 23, true],
    ['overnight', 4, true],
    ['overnight', 5, false],
  ] as const)('%s at %i is %s', (time, hour, inside) => {
    expect(inTimeOfDay(hour, time)).toBe(inside)
  })
})

describe('selectEntries', () => {
  const mixed: FixtureEntry[] = [
    { pin: 'ford', day: 100, category: 'premises' },
    { pin: 'ford', day: 100, category: 'traffic' },
    { pin: 'ford', day: 100, category: 'alarms' },
    { pin: 'ford', day: 100, category: 'checks' },
  ]

  it('keeps every kind for all activity, and one kind when one is chosen', () => {
    expect(kept(mixed, {})).toEqual([1, 1, 1, 1])
    expect(kept(mixed, { kind: 'traffic' })).toEqual([0, 1, 0, 0])
    expect(kept(mixed, { kind: 'place' })).toEqual([1, 0, 0, 0])
    expect(kept(mixed, { kind: 'alarms' })).toEqual([0, 0, 1, 0])
  })

  it('counts a date range back from the last day the log covers', () => {
    const entries = [
      { pin: 'ford', day: 70 },
      { pin: 'ford', day: 71 },
      { pin: 'ford', day: 100 },
    ]
    expect(lastDayOf(decode(entries))).toBe(100)
    expect(kept(entries, { range: '30' })).toEqual([0, 1, 1])
  })

  it('keeps the hours of the chosen time of day', () => {
    const entries = [
      { pin: 'ford', day: 1, hour: 3 },
      { pin: 'ford', day: 1, hour: 12 },
    ]
    expect(kept(entries, { time: 'night' })).toEqual([1, 0])
  })

  it('keeps one officer, and nothing for an officer no entry names', () => {
    const entries = [
      { pin: 'ford', day: 1, officer: 'C. Day' },
      { pin: 'ford', day: 1, officer: null },
    ]
    expect(kept(entries, { officer: 'C. Day' })).toEqual([1, 0])
    expect(kept(entries, { officer: 'Nobody' })).toEqual([0, 0])
  })

  it('counts only calls from the public about a place for Places', () => {
    const entries: FixtureEntry[] = [
      { pin: 'ford', day: 1, category: 'premises', source: 'Telephone' },
      { pin: 'ford', day: 1, category: 'premises', source: 'Initiated' },
      { pin: 'ford', day: 1, category: 'traffic', source: 'Telephone' },
      { pin: 'ford', day: 1, category: 'alarms', source: 'Alarm System' },
      { pin: 'main-st', day: 1, category: 'premises', source: 'Telephone' },
      { pin: STATION_ID, day: 1, category: 'premises', source: 'Walk-In' },
    ]
    expect(kept(entries, { kind: 'traffic' }, 'public')).toEqual([1, 0, 0, 0, 0, 0])
  })
})

describe('filteredAddresses', () => {
  it('gives the counts the export gives when every entry is kept', () => {
    const entries: FixtureEntry[] = [
      ...times(3, { pin: 'ford', day: 1, category: 'premises' }),
      ...times(2, { pin: 'ford', day: 1, category: 'traffic' }),
      ...times(4, { pin: 'main-st', day: 1, category: 'traffic' }),
      { pin: 'main-st', day: 1, category: 'alarms' },
    ]
    const activity = decode(entries)
    const all = new Uint8Array(activity.size).fill(1)
    const [ford, main] = filteredAddresses(ADDRESSES, activity, all)
    // A place leaves out road traffic, and a road keeps it.
    expect([ford.count, ford.traffic_count]).toEqual([3, 2])
    expect([main.count, main.traffic_count]).toEqual([5, 4])
  })

  it('leaves a place with only traffic as traffic nearby, as the map shows it', () => {
    const entries = [
      { pin: 'ford', day: 1, category: 'premises' },
      { pin: 'ford', day: 1, category: 'traffic' },
    ]
    const activity = decode(entries)
    const traffic = selectEntries(
      activity,
      ADDRESSES,
      { ...DEFAULT_FILTERS, kind: 'traffic' },
      'all',
    )
    const [ford] = filteredAddresses(ADDRESSES, activity, traffic)
    expect([ford.count, ford.traffic_count]).toEqual([0, 1])
  })
})

describe('tally', () => {
  it('leaves walk-ins out of the time to arrive and keeps every time on scene', () => {
    const entries: FixtureEntry[] = [
      { pin: 'ford', day: 1, source: 'Telephone', response: 6, scene: 20 },
      { pin: 'ford', day: 1, source: 'Walk-In', response: 0, scene: 10 },
      { pin: 'ford', day: 1, source: 'Initiated', scene: 5 },
    ]
    const activity = decode(entries)
    const town = tally(activity, new Uint8Array(3).fill(1), wholeTown).get(TOWN)!
    expect(town.n).toBe(3)
    expect(town.responses).toEqual([6])
    expect(town.scenes).toEqual([20, 10, 5])
    expect(town.initiated).toBe(1)
  })

  it("puts a listed place's entries on its street's card, and keeps the rest on their own", () => {
    const bank = address('bank', { hidden: true, street_id: 'main-st' })
    const pins = [FORD, MAIN, bank]
    const activity = decodeActivity(
      activityFile(
        pins.map((a) => a.id),
        [
          { pin: 'main-st', day: 1 },
          { pin: 'bank', day: 1 },
          { pin: 'bank', day: 2 },
          { pin: 'ford', day: 1 },
        ],
      ),
      pins,
    )
    const cards = tally(activity, new Uint8Array(4).fill(1), cardGroupOf(activity, pins))
    expect(cards.get(1)?.n).toBe(3)
    expect(cards.get(0)?.n).toBe(1)
    expect(cards.has(2)).toBe(false)
  })

  it('counts night as 7pm to 7am', () => {
    const activity = decode([
      { pin: 'ford', day: 1, hour: 19 },
      { pin: 'ford', day: 1, hour: 7 },
      { pin: 'ford', day: 1, hour: 6 },
    ])
    expect(tally(activity, new Uint8Array(3).fill(1), wholeTown).get(TOWN)!.night).toBe(2)
  })
})

describe('rangeLabel', () => {
  it('names the months a range covers, starting no earlier than since', () => {
    // Day 322 is November 19, 2026.
    expect(rangeLabel(SINCE, 322, '365')).toBe('Jan to Nov 2026')
    expect(rangeLabel(SINCE, 322, '90')).toBe('Aug to Nov 2026')
    expect(rangeLabel(SINCE, 322, '30')).toBe('Oct to Nov 2026')
    expect(rangeLabel(SINCE, 20, '30')).toBe('Jan 2026')
  })

  it('names both years across a year end', () => {
    expect(rangeLabel(SINCE, 400, '90')).toBe('Nov 2026 to Feb 2027')
  })
})

describe('typical', () => {
  it('is the middle value, and null with too few to trust', () => {
    expect(typical([30, 5, 10, 20, 40, 15, 25, 35, 45, 50])).toBe(30)
    expect(typical([5, 10, 20])).toBeNull()
  })
})
