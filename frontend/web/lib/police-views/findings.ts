import { CATEGORIES } from '@/lib/police-map/categories'
import { plainType } from '@/lib/police-map/labels'
import { CATEGORY_KEYS, UNTIMED, type Activity } from './activity'
import { lastDayOf } from './select'
import { weekCount } from './counts'

export type WeekFlag = 'thin' | 'partial' | null

// A week with under half the usual activity is missing logs, not a quiet week, and the last
// week is still filling in unless the log covers all seven of its days. Both are judged on
// every entry, so a filter cannot make a quiet stretch look like missing logs.
export function weekFlags(activity: Activity): WeekFlag[] {
  const totals = new Array(weekCount(activity)).fill(0)
  for (let i = 0; i < activity.size; i++) totals[activity.week[i]]++
  const last = totals.length - 1
  const partial = lastDayOf(activity) % 7 !== 6
  const full = totals.filter((_, week) => !(partial && week === last)).sort((a, b) => a - b)
  const usual = full[Math.floor(full.length / 2)] ?? 0
  return totals.map((total, week) => {
    if (partial && week === last) return 'partial'
    return total < usual / 2 ? 'thin' : null
  })
}

const STRETCH = 3
const WEEKDAYS = [1, 2, 3, 4, 5]
const WEEKEND = [0, 6]
const ALL_DAYS = [0, 1, 2, 3, 4, 5, 6]

// grid[weekday][hour]. The average per day over a three-hour stretch, wrapping past midnight.
function perDay(grid: number[][], days: number[], start: number): number {
  let sum = 0
  for (const day of days) {
    for (let h = 0; h < STRETCH; h++) sum += grid[day][(start + h) % 24]
  }
  return sum / days.length
}

function bestStart(grid: number[][], days: number[], better: (a: number, b: number) => boolean) {
  let best = 0
  for (let start = 1; start < 24; start++) {
    if (better(perDay(grid, days, start), perDay(grid, days, best))) best = start
  }
  return best
}

export interface BusyStretch {
  weekdays: boolean
  start: number
  quietStart: number
}

// The three-hour stretch with the most activity per day, on weekdays or on weekends, and the
// quietest stretch over the whole week. Null when there is no activity.
export function busyStretch(grid: number[][]): BusyStretch | null {
  if (grid.every((row) => row.every((v) => v === 0))) return null
  const weekday = bestStart(grid, WEEKDAYS, (a, b) => a > b)
  const weekend = bestStart(grid, WEEKEND, (a, b) => a > b)
  const weekdays = perDay(grid, WEEKDAYS, weekday) >= perDay(grid, WEEKEND, weekend)
  return {
    weekdays,
    start: weekdays ? weekday : weekend,
    quietStart: bestStart(grid, ALL_DAYS, (a, b) => a < b),
  }
}

export function partOfDay(hour: number): string {
  if (hour < 5) return 'nights'
  if (hour < 12) return 'mornings'
  if (hour < 17) return 'afternoons'
  if (hour < 21) return 'evenings'
  return 'nights'
}

// "9am", "noon", "midnight".
export function clock(hour: number): string {
  const h = ((hour % 24) + 24) % 24
  if (h === 0) return 'midnight'
  if (h === 12) return 'noon'
  return h < 12 ? `${h}am` : `${h - 12}pm`
}

export interface TypicalWeek {
  // Rounded to the nearest ten from 100 up, so it reads as "about".
  perWeek: number
  steady: boolean
  // The month with the most activity per full week, 0 for January.
  topMonth: number
}

// Weeks under 15% apart from their average count as steady.
const STEADY = 0.15

export interface WeekRange {
  // The first week the date range touches, an index into the year's weeks.
  first: number
  // The flags of the weeks from `first` on.
  flags: WeekFlag[]
}

// The weeks a date range covers. A range that starts mid-week makes its first week partial,
// so it cannot pass for a quiet week.
export function weeksInRange(flags: WeekFlag[], firstDay: number): WeekRange {
  const first = Math.floor(Math.max(0, firstDay) / 7)
  const inRange = flags.slice(first)
  if (firstDay > 0 && firstDay % 7 !== 0 && inRange.length > 0) inRange[0] = 'partial'
  return { first, flags: inRange }
}

// A typical full week, and whether the range was steady or had a clear high. `totals` and
// `flags` start at week `firstWeek`. Incomplete weeks are left out of both.
export function typicalWeek(
  totals: number[],
  flags: WeekFlag[],
  since: string,
  firstWeek = 0,
): TypicalWeek | null {
  const full = totals.filter((_, week) => !flags[week])
  if (full.length === 0 || full.every((v) => v === 0)) return null
  const sorted = [...full].sort((a, b) => a - b)
  const median = sorted[Math.floor(sorted.length / 2)]
  const mean = full.reduce((a, b) => a + b, 0) / full.length
  const spread = Math.sqrt(full.reduce((a, v) => a + (v - mean) ** 2, 0) / full.length) / mean

  const start = new Date(`${since}T00:00:00Z`).getTime()
  const byMonth = new Array(12).fill(0)
  const weeksIn = new Array(12).fill(0)
  totals.forEach((total, week) => {
    if (flags[week]) return
    // A week belongs to the month of its middle day.
    const month = new Date(start + ((firstWeek + week) * 7 + 3) * 86_400_000).getUTCMonth()
    byMonth[month] += total
    weeksIn[month]++
  })
  const rate = byMonth.map((total, month) => (weeksIn[month] ? total / weeksIn[month] : 0))
  return {
    perWeek: median >= 100 ? Math.round(median / 10) * 10 : median,
    steady: spread < STEADY,
    topMonth: rate.indexOf(Math.max(...rate)),
  }
}

export interface StayRow {
  type: string
  label: string
  n: number
  // Minutes on scene: the typical visit, and the middle half of visits.
  typical: number
  low: number
  high: number
}

// A type needs this many timed visits to get a bar.
const MIN_VISITS = 20
const STAY_ROWS = 10
// A paid detail is a shift, not a visit.
const DETAIL = 'Detail Special Outside'

// Every timed visit, as [type, minutes]. Paperwork is not a visit and a paid detail is a
// shift, so neither counts.
function timedVisits(activity: Activity, kept: Uint8Array): [number, number][] {
  const admin = CATEGORY_KEYS.indexOf('admin')
  const detail = activity.types.indexOf(DETAIL)
  const visits: [number, number][] = []
  for (let i = 0; i < activity.size; i++) {
    if (!kept[i] || activity.scene[i] === UNTIMED) continue
    if (activity.category[i] === admin || activity.type[i] === detail) continue
    visits.push([activity.type[i], activity.scene[i]])
  }
  return visits
}

// The minutes of every visit, for the typical visit overall.
export function allVisits(activity: Activity, kept: Uint8Array): number[] {
  return timedVisits(activity, kept).map(([, minutes]) => minutes)
}

// The typical minutes on scene for the most common types, longest first.
export function stayRows(activity: Activity, kept: Uint8Array): StayRow[] {
  const byType = new Map<number, number[]>()
  for (const [type, minutes] of timedVisits(activity, kept)) {
    const visits = byType.get(type) ?? []
    visits.push(minutes)
    byType.set(type, visits)
  }
  const at = (sorted: number[], share: number) =>
    sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * share))]
  return [...byType]
    .filter(([, visits]) => visits.length >= MIN_VISITS)
    .sort((a, b) => b[1].length - a[1].length || a[0] - b[0])
    .slice(0, STAY_ROWS)
    .map(([type, visits]) => {
      const sorted = [...visits].sort((a, b) => a - b)
      return {
        type: activity.types[type] ?? 'Unknown',
        label: plainType(activity.types[type]),
        n: sorted.length,
        typical: at(sorted, 0.5),
        low: at(sorted, 0.25),
        high: at(sorted, 0.75),
      }
    })
    .sort((a, b) => b.typical - a.typical || a.label.localeCompare(b.label))
}

// Labels closer than this many pixels would overlap.
const LABEL_GAP = 15

export interface Label {
  key: string
  label: string
  color: string
  total: number
  y: number
}

// Each label sits level with the middle of its band in the last full week, then labels are
// pushed apart so none overlap, and back up if the push ran past the bottom.
export function directLabels(
  weeks: number[][],
  flags: WeekFlag[],
  kindTotals: number[],
  max: number,
  height: number,
): Label[] {
  let lastFull = weeks.length - 1
  while (lastFull > 0 && flags[lastFull]) lastFull--
  const week = weeks[lastFull] ?? []
  let below = 0
  const labels: Label[] = []
  CATEGORIES.forEach((kind, k) => {
    const value = week[k] ?? 0
    const middle = ((below + value / 2) / max) * height
    below += value
    if (kindTotals[k] > 0) {
      labels.push({
        key: kind.key,
        label: kind.label,
        color: kind.color,
        total: kindTotals[k],
        y: height - middle,
      })
    }
  })
  labels.sort((a, b) => a.y - b.y)
  for (let k = 1; k < labels.length; k++)
    labels[k].y = Math.max(labels[k].y, labels[k - 1].y + LABEL_GAP)
  const overflow = labels.length ? labels[labels.length - 1].y - (height - 6) : 0
  if (overflow > 0) labels.forEach((label) => (label.y -= overflow))
  for (let k = labels.length - 2; k >= 0; k--)
    labels[k].y = Math.min(labels[k].y, labels[k + 1].y - LABEL_GAP)
  return labels
}

// The heat map's color step for a count: 0 for none, then 1 to `steps`, the busiest last.
export function heatStep(value: number, max: number, steps: number): number {
  if (value <= 0) return 0
  return Math.min(steps, Math.floor(value / (max / steps)) + 1)
}

export interface HeatKeyRow {
  step: number
  low: number
  high: number
}

// The counts each step covers, found by putting every count through `heatStep`, so the key
// always matches the colors. A step no whole count falls in is left out.
export function heatKey(max: number, steps: number): HeatKeyRow[] {
  const rows: HeatKeyRow[] = []
  for (let value = 1; value <= max; value++) {
    const step = heatStep(value, max, steps)
    const last = rows.at(-1)
    if (last?.step === step) last.high = value
    else rows.push({ step, low: value, high: value })
  }
  return rows
}
