import { CATEGORIES, type CategoryKey } from '@/lib/police-map/categories'
import type { Address } from '@/lib/types'

// data/activity.json, as report-gen writes it. Every column has one value per entry.
export interface ActivityFile {
  since: string
  pins: string[]
  lookups: {
    category: string[]
    type: (string | null)[]
    disposition: (string | null)[]
    source: (string | null)[]
    officer: (string | null)[]
  }
  columns: {
    pin: number[]
    minute: number[]
    category: number[]
    type: number[]
    disposition: number[]
    source: number[]
    officer: number[]
    response: number[]
    scene: number[]
  }
}

// A response or a time on scene that was not timed.
export const UNTIMED = -1

const MINUTES_PER_DAY = 24 * 60

// The entries, decoded once, with what every view filters or counts by worked out ahead.
// `pin` is an index into the page's addresses, so a view can read an entry's place directly.
export interface Activity {
  since: string
  size: number
  pin: Int32Array
  day: Int32Array
  week: Int32Array
  hour: Uint8Array
  weekday: Uint8Array
  category: Uint8Array
  type: Int32Array
  disposition: Int32Array
  source: Int32Array
  officer: Int32Array
  response: Int32Array
  scene: Int32Array
  types: (string | null)[]
  dispositions: (string | null)[]
  sources: (string | null)[]
  officers: (string | null)[]
}

export const CATEGORY_KEYS: CategoryKey[] = CATEGORIES.map((c) => c.key)

// Entries whose pin the page does not have are dropped, so a stale file can never point a
// count at the wrong place.
export function decodeActivity(file: ActivityFile, addresses: Address[]): Activity {
  const byId = new Map(addresses.map((address, index) => [address.id, index]))
  const pinIndex = file.pins.map((id) => byId.get(id) ?? -1)
  const categoryIndex = file.lookups.category.map((key) =>
    CATEGORY_KEYS.indexOf(key as CategoryKey),
  )
  const firstWeekday = new Date(`${file.since}T00:00:00Z`).getUTCDay()
  const columns = file.columns

  const kept: number[] = []
  for (let i = 0; i < columns.pin.length; i++) {
    if (pinIndex[columns.pin[i]] >= 0 && categoryIndex[columns.category[i]] >= 0) kept.push(i)
  }

  const size = kept.length
  const activity: Activity = {
    since: file.since,
    size,
    pin: new Int32Array(size),
    day: new Int32Array(size),
    week: new Int32Array(size),
    hour: new Uint8Array(size),
    weekday: new Uint8Array(size),
    category: new Uint8Array(size),
    type: new Int32Array(size),
    disposition: new Int32Array(size),
    source: new Int32Array(size),
    officer: new Int32Array(size),
    response: new Int32Array(size),
    scene: new Int32Array(size),
    types: file.lookups.type,
    dispositions: file.lookups.disposition,
    sources: file.lookups.source,
    officers: file.lookups.officer,
  }
  kept.forEach((from, to) => {
    const minute = columns.minute[from]
    const day = Math.floor(minute / MINUTES_PER_DAY)
    activity.pin[to] = pinIndex[columns.pin[from]]
    activity.day[to] = day
    activity.week[to] = Math.floor(day / 7)
    activity.hour[to] = Math.floor((minute - day * MINUTES_PER_DAY) / 60)
    activity.weekday[to] = (firstWeekday + day) % 7
    activity.category[to] = categoryIndex[columns.category[from]]
    activity.type[to] = columns.type[from]
    activity.disposition[to] = columns.disposition[from]
    activity.source[to] = columns.source[from]
    activity.officer[to] = columns.officer[from]
    activity.response[to] = columns.response[from]
    activity.scene[to] = columns.scene[from]
  })
  return activity
}
