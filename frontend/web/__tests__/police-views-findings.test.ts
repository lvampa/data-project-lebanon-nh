import { describe, expect, it } from 'vitest'
import { decodeActivity } from '@/lib/police-views/activity'
import {
  busyStretch,
  clock,
  directLabels,
  heatKey,
  heatStep,
  leftOutLine,
  partOfDay,
  stayRows,
  typicalWeek,
  weekFlags,
  weeksInRange,
} from '@/lib/police-views/findings'
import { SINCE, activityFile, address, times, type FixtureEntry } from './police-views-fixture'

describe('leftOutLine', () => {
  it('names every entry the Officers list leaves out', () => {
    expect(leftOutLine(4929, 10, 63, 25)).toBe(
      'Left out: 4,929 entries name no officer, and 10 officers with fewer than 25 have 63 more.',
    )
    expect(leftOutLine(1, 0, 0, 25)).toBe('Left out: 1 entry names no officer.')
    expect(leftOutLine(0, 1, 3, 25)).toBe('Left out: 1 officer with fewer than 25 has 3 more.')
    expect(leftOutLine(0, 0, 0, 25)).toBe('')
  })
})

const FORD = address('ford')

function decode(entries: FixtureEntry[]) {
  return decodeActivity(activityFile(['ford'], entries), [FORD])
}

// `perWeek[w]` entries in week w, spread over its days.
function weeks(perWeek: number[], lastDay?: number): FixtureEntry[] {
  const entries = perWeek.flatMap((n, week) => times(n, { pin: 'ford', day: week * 7 + 1 }))
  if (lastDay !== undefined) entries.push({ pin: 'ford', day: lastDay })
  return entries
}

describe('weekFlags', () => {
  it('marks a week with under half the usual activity as missing logs', () => {
    // The log runs to day 34, the last day of week 4, so no week is partial.
    expect(weekFlags(decode(weeks([40, 42, 15, 41, 40], 34)))).toEqual([
      null,
      null,
      'thin',
      null,
      null,
    ])
  })

  it('marks the last week as still filling in until all seven days are logged', () => {
    expect(weekFlags(decode(weeks([40, 42, 41, 5], 23))).at(-1)).toBe('partial')
  })
})

function grid(fill: (weekday: number, hour: number) => number): number[][] {
  return Array.from({ length: 7 }, (_, day) => Array.from({ length: 24 }, (_, h) => fill(day, h)))
}

describe('busyStretch', () => {
  it('finds the busiest weekday stretch and the quietest stretch', () => {
    const weekdayMornings = grid(
      (day, h) => (day >= 1 && day <= 5 && h >= 9 && h < 12 ? 30 : 5) - (h >= 3 && h < 6 ? 4 : 0),
    )
    expect(busyStretch(weekdayMornings)).toEqual({ weekdays: true, start: 9, quietStart: 3 })
  })

  it('finds a weekend stretch when weekends are busier', () => {
    const lateWeekends = grid((day, h) => ((day === 0 || day === 6) && h >= 22 ? 40 : 2))
    expect(busyStretch(lateWeekends)?.weekdays).toBe(false)
    expect(busyStretch(lateWeekends)?.start).toBe(21)
  })

  it('is null with no activity', () => {
    expect(busyStretch(grid(() => 0))).toBeNull()
  })
})

describe('the words for a stretch', () => {
  it.each([
    [0, 'midnight'],
    [9, '9am'],
    [12, 'noon'],
    [15, '3pm'],
    [24, 'midnight'],
    [25, '1am'],
  ])('clock(%i) is %s', (hour, word) => {
    expect(clock(hour)).toBe(word)
  })

  it('names the part of the day a stretch is in', () => {
    expect([3, 10, 14, 19, 22].map(partOfDay)).toEqual([
      'nights',
      'mornings',
      'afternoons',
      'evenings',
      'nights',
    ])
  })
})

describe('typicalWeek', () => {
  it('calls a year steady when full weeks stay close, rounded to tens', () => {
    expect(typicalWeek([432, 441, 428, 450], [null, null, null, null], SINCE)).toEqual({
      perWeek: 440,
      steady: true,
      topMonth: 0,
    })
  })

  it('names the busiest month when weeks vary, and leaves incomplete weeks out', () => {
    // Weeks 8 to 11 are in March. The thin week would be the lowest if it counted.
    const totals = [100, 100, 100, 100, 100, 100, 100, 100, 300, 300, 300, 300, 2]
    const flags = totals.map((_, week) => (week === 12 ? ('thin' as const) : null))
    const found = typicalWeek(totals, flags, SINCE)!
    expect(found.steady).toBe(false)
    expect(found.topMonth).toBe(2)
  })
})

describe('weeksInRange', () => {
  const year = [null, null, 'thin', null, null, 'partial'] as const

  it('starts at the week the range starts in, and marks it partial when it starts mid-week', () => {
    // Day 16 is the third day of week 2.
    expect(weeksInRange([...year], 16)).toEqual({
      first: 2,
      flags: ['partial', null, null, 'partial'],
    })
  })

  it('keeps a first week whole when the range starts on its first day', () => {
    expect(weeksInRange([...year], 21).flags[0]).toBeNull()
    expect(weeksInRange([...year], -40)).toEqual({ first: 0, flags: [...year] })
  })
})

describe('typicalWeek under a date range', () => {
  it('counts only the weeks in the range, and names their month', () => {
    // Weeks 30 to 33 fall in August. The weeks before the range are not passed in.
    const found = typicalWeek([420, 440, 430, 450], [null, null, null, null], SINCE, 30)!
    expect(found.perWeek).toBe(440)
    expect(found.topMonth).toBe(7)
  })
})

describe('heatStep and heatKey', () => {
  it('give every count exactly one step, the busiest in the last', () => {
    expect([0, 1, 24, 25, 99, 100].map((v) => heatStep(v, 100, 4))).toEqual([0, 1, 1, 2, 4, 4])
    expect(heatKey(100, 4)).toEqual([
      { step: 1, low: 1, high: 24 },
      { step: 2, low: 25, high: 49 },
      { step: 3, low: 50, high: 74 },
      { step: 4, low: 75, high: 100 },
    ])
  })

  it('leaves out a step no whole count falls in', () => {
    expect(heatKey(2, 4)).toEqual([
      { step: 3, low: 1, high: 1 },
      { step: 4, low: 2, high: 2 },
    ])
  })
})

describe('directLabels', () => {
  // Kinds in CATEGORIES order: incidents, traffic, alarms, patrols and checks, paperwork.
  const totals = [100, 50, 10, 5, 0]

  it('labels each kind that has activity, beside the last full week', () => {
    const weeks = [
      [60, 30, 6, 3, 0],
      [1, 1, 0, 0, 0],
    ]
    const labels = directLabels(weeks, [null, 'partial'], totals, 100, 150)
    expect(labels.map((label) => label.label)).toEqual([
      'Patrols and checks',
      'Alarms',
      'Traffic',
      'Incidents here',
    ])
    // The biggest band is at the bottom of the stack, so its label is lowest.
    expect(labels.at(-1)!.y).toBeCloseTo(150 - (30 / 100) * 150)
  })

  it('pushes labels apart so none overlap, and keeps them inside the chart', () => {
    const labels = directLabels([[100, 1, 1, 1, 0]], [null], totals, 103, 150)
    const ys = labels.map((label) => label.y).sort((a, b) => a - b)
    for (let k = 1; k < ys.length; k++) expect(ys[k] - ys[k - 1]).toBeGreaterThanOrEqual(15)
    expect(Math.max(...ys)).toBeLessThanOrEqual(144)
  })
})

describe('stayRows', () => {
  it('ranks common types by their typical visit and leaves out paperwork and details', () => {
    const entries: FixtureEntry[] = [
      ...times(20, { pin: 'ford', day: 1, type: 'Welfare Check', scene: 20 }),
      ...times(30, { pin: 'ford', day: 1, type: 'Motor Vehicle Stop', scene: 10 }),
      ...times(25, { pin: 'ford', day: 1, type: 'Detail Special Outside', scene: 400 }),
      ...times(25, { pin: 'ford', day: 1, type: 'Fingerprinting', category: 'admin', scene: 60 }),
      ...times(19, { pin: 'ford', day: 1, type: 'Arrest', scene: 90 }),
    ]
    const activity = decode(entries)
    const rows = stayRows(activity, new Uint8Array(activity.size).fill(1))
    expect(rows.map((row) => [row.label, row.typical, row.n])).toEqual([
      ['Welfare check', 20, 20],
      ['Traffic stop', 10, 30],
    ])
  })
})
