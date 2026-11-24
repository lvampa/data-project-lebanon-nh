// The views, the filters they share, and how both live in the URL query, so a filtered view
// can be shared. Defaults are left out, so the plain page keeps its plain URL.

import { ROADS_MODES, type RoadsMode } from './roads'

export const VIEWS = [
  { id: 'map', label: 'Map' },
  { id: 'places', label: 'Places' },
  { id: 'roads', label: 'Roads' },
  { id: 'busy', label: 'Busy times' },
  { id: 'officers', label: 'Officers' },
] as const
export type View = (typeof VIEWS)[number]['id']

// One kind at a time. `category` is the one category the kind keeps; "all" keeps every one.
export const KINDS = [
  { id: 'all', label: 'All activity', category: null },
  { id: 'place', label: 'About a place', category: 'premises' },
  { id: 'traffic', label: 'Traffic', category: 'traffic' },
  { id: 'alarms', label: 'Alarms', category: 'alarms' },
] as const
export type Kind = (typeof KINDS)[number]['id']

export const TIMES = [
  { id: 'all', label: 'Any time of day' },
  { id: 'day', label: 'Daytime, 7am to 7pm' },
  { id: 'night', label: 'Night, 7pm to 7am' },
  { id: 'overnight', label: 'Overnight, 11pm to 5am' },
] as const
export type TimeOfDay = (typeof TIMES)[number]['id']

export const RANGES = [
  { id: '365', label: 'Last 12 months', days: 365 },
  { id: '90', label: 'Last 90 days', days: 90 },
  { id: '30', label: 'Last 30 days', days: 30 },
] as const
export type Range = (typeof RANGES)[number]['id']

export interface Filters {
  kind: Kind
  time: TimeOfDay
  range: Range
  // An officer's name as the log spells it.
  officer: string | null
}

export const DEFAULT_FILTERS: Filters = { kind: 'all', time: 'all', range: '365', officer: null }

export function isDefault(filters: Filters): boolean {
  return (
    filters.kind === DEFAULT_FILTERS.kind &&
    filters.time === DEFAULT_FILTERS.time &&
    filters.range === DEFAULT_FILTERS.range &&
    filters.officer === DEFAULT_FILTERS.officer
  )
}

// The filters behind the Filters button on a phone: everything but the kind, whose chips
// stay in view.
export function sheetFilterCount(filters: Filters): number {
  return [
    filters.time !== DEFAULT_FILTERS.time,
    filters.range !== DEFAULT_FILTERS.range,
    filters.officer !== DEFAULT_FILTERS.officer,
  ].filter(Boolean).length
}

export function rangeDays(range: Range): number {
  return RANGES.find((r) => r.id === range)!.days
}

export function inTimeOfDay(hour: number, time: TimeOfDay): boolean {
  if (time === 'day') return hour >= 7 && hour < 19
  if (time === 'night') return hour >= 19 || hour < 7
  if (time === 'overnight') return hour >= 23 || hour < 5
  return true
}

// Night on a card or in a finding is always 7pm to 7am, the same as the Night filter.
export const isNight = (hour: number) => inTimeOfDay(hour, 'night')

function oneOf<T extends string>(value: string | null, allowed: readonly { id: T }[], fallback: T) {
  return allowed.some((option) => option.id === value) ? (value as T) : fallback
}

// A value the page does not know falls back to its default, so an old or mistyped link
// still opens.
export function readQuery(search: string): { view: View; filters: Filters; mode: RoadsMode } {
  const query = new URLSearchParams(search)
  return {
    view: oneOf(query.get('view'), VIEWS, 'map'),
    mode: oneOf(query.get('mode'), ROADS_MODES, 'roads'),
    filters: {
      kind: oneOf(query.get('kind'), KINDS, DEFAULT_FILTERS.kind),
      time: oneOf(query.get('time'), TIMES, DEFAULT_FILTERS.time),
      range: oneOf(query.get('range'), RANGES, DEFAULT_FILTERS.range),
      officer: query.get('officer') || null,
    },
  }
}

// "?view=places&time=night", or "" for the map with the default filters.
export function writeQuery(view: View, filters: Filters, mode: RoadsMode): string {
  const query = new URLSearchParams()
  if (view !== 'map') query.set('view', view)
  if (view === 'roads' && mode !== 'roads') query.set('mode', mode)
  if (filters.kind !== DEFAULT_FILTERS.kind) query.set('kind', filters.kind)
  if (filters.time !== DEFAULT_FILTERS.time) query.set('time', filters.time)
  if (filters.range !== DEFAULT_FILTERS.range) query.set('range', filters.range)
  if (filters.officer) query.set('officer', filters.officer)
  const text = query.toString()
  return text ? `?${text}` : ''
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// The months a range covers, such as "Jan to Nov 2026". It starts no earlier than `since`,
// the first day published, and ends on `lastDay`, days after it.
export function rangeLabel(since: string, lastDay: number, range: Range): string {
  const start = new Date(`${since}T00:00:00Z`).getTime()
  const dayAt = (day: number) => new Date(start + day * 86_400_000)
  const from = dayAt(Math.max(0, lastDay - rangeDays(range) + 1))
  const to = dayAt(lastDay)
  const [fromMonth, toMonth] = [MONTHS[from.getUTCMonth()], MONTHS[to.getUTCMonth()]]
  const [fromYear, toYear] = [from.getUTCFullYear(), to.getUTCFullYear()]
  if (fromYear !== toYear) return `${fromMonth} ${fromYear} to ${toMonth} ${toYear}`
  return fromMonth === toMonth ? `${toMonth} ${toYear}` : `${fromMonth} to ${toMonth} ${toYear}`
}

// What a count of kept entries is made of, in words.
export function nounFor(kind: Kind): string {
  return {
    all: 'log entries',
    place: 'entries about a place',
    traffic: 'traffic stops and calls',
    alarms: 'alarms',
  }[kind]
}
