import type { ActivityFile } from '@/lib/police-views/activity'
import type { Address } from '@/lib/types'

// 2026-01-01 is a Thursday.
export const SINCE = '2026-01-01'

export interface FixtureEntry {
  pin: string
  // Day after `since`, and the hour of that day.
  day: number
  hour?: number
  category?: string
  type?: string | null
  disposition?: string | null
  source?: string | null
  officer?: string | null
  response?: number
  scene?: number
}

export function address(id: string, extra: Partial<Address> = {}): Address {
  return {
    id,
    kind: 'place',
    raw_address: id,
    normalized_address: id,
    count: 0,
    traffic_count: 0,
    nearby_traffic: 0,
    lat: 43.64,
    lng: -72.25,
    precision: 'exact',
    street_id: null,
    hidden: false,
    ...extra,
  }
}

// An activity.json with each text value once in its lookup, as report-gen writes it.
export function activityFile(pins: string[], entries: FixtureEntry[]): ActivityFile {
  const lookups = {
    category: [] as string[],
    type: [] as (string | null)[],
    disposition: [] as (string | null)[],
    source: [] as (string | null)[],
    officer: [] as (string | null)[],
  }
  const code = <T>(list: T[], value: T) => {
    const at = list.indexOf(value)
    if (at >= 0) return at
    list.push(value)
    return list.length - 1
  }
  const columns: ActivityFile['columns'] = {
    pin: [],
    minute: [],
    category: [],
    type: [],
    disposition: [],
    source: [],
    officer: [],
    response: [],
    scene: [],
  }
  for (const entry of entries) {
    columns.pin.push(pins.indexOf(entry.pin))
    columns.minute.push(entry.day * 1440 + (entry.hour ?? 12) * 60)
    columns.category.push(code(lookups.category, entry.category ?? 'premises'))
    columns.type.push(code(lookups.type, entry.type === undefined ? 'Welfare Check' : entry.type))
    columns.disposition.push(code(lookups.disposition, entry.disposition ?? null))
    columns.source.push(
      code(lookups.source, entry.source === undefined ? 'Telephone' : entry.source),
    )
    columns.officer.push(code(lookups.officer, entry.officer ?? null))
    columns.response.push(entry.response ?? -1)
    columns.scene.push(entry.scene ?? -1)
  }
  return { since: SINCE, pins, lookups, columns }
}

// `n` copies of one entry.
export function times(n: number, entry: FixtureEntry): FixtureEntry[] {
  return Array.from({ length: n }, () => ({ ...entry }))
}
