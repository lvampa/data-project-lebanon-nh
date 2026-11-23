import type { Address } from '@/lib/types'
import { CATEGORY_KEYS, UNTIMED, type Activity } from './activity'
import { isNight } from './filters'

// Fewer timed entries than this make a typical time too shaky to show.
export const MIN_TIMED = 10

// The addresses with the counts of the kept entries, in the shape the map already reads:
// a place's count leaves out road traffic, a road's keeps it, and traffic is counted apart.
// Everything else about an address, such as hidden places and their street, is unchanged.
export function filteredAddresses(
  addresses: Address[],
  activity: Activity,
  kept: Uint8Array,
): Address[] {
  const count = new Int32Array(addresses.length)
  const traffic = new Int32Array(addresses.length)
  const trafficCategory = CATEGORY_KEYS.indexOf('traffic')
  for (let i = 0; i < activity.size; i++) {
    if (!kept[i]) continue
    const pin = activity.pin[i]
    if (activity.category[i] === trafficCategory) {
      traffic[pin]++
      if (addresses[pin].kind === 'road') count[pin]++
    } else {
      count[pin]++
    }
  }
  return addresses.map((address, pin) => ({
    ...address,
    count: count[pin],
    traffic_count: traffic[pin],
  }))
}

// What a view needs to know about one group of entries: a pin, an officer, or the town.
export interface Tally {
  n: number
  hours: number[]
  weekdays: number[]
  weeks: number[]
  night: number
  // Entries an officer started.
  initiated: number
  types: Map<number, number>
  categories: number[]
  responses: number[]
  scenes: number[]
}

function emptyTally(weeks: number): Tally {
  return {
    n: 0,
    hours: new Array(24).fill(0),
    weekdays: new Array(7).fill(0),
    weeks: new Array(weeks).fill(0),
    night: 0,
    initiated: 0,
    types: new Map(),
    categories: new Array(CATEGORY_KEYS.length).fill(0),
    responses: [],
    scenes: [],
  }
}

export function weekCount(activity: Activity): number {
  let last = 0
  for (let i = 0; i < activity.size; i++) if (activity.week[i] > last) last = activity.week[i]
  return last + 1
}

// One pass over the kept entries, adding each to the tally of its group. `groupOf` returns
// -1 for an entry that belongs to no group.
export function tally(
  activity: Activity,
  kept: Uint8Array,
  groupOf: (entry: number) => number,
): Map<number, Tally> {
  const weeks = weekCount(activity)
  const initiated = activity.sources.indexOf('Initiated')
  const walkIn = activity.sources.indexOf('Walk-In')
  const tallies = new Map<number, Tally>()
  for (let i = 0; i < activity.size; i++) {
    if (!kept[i]) continue
    const group = groupOf(i)
    if (group < 0) continue
    let t = tallies.get(group)
    if (!t) tallies.set(group, (t = emptyTally(weeks)))
    t.n++
    t.hours[activity.hour[i]]++
    t.weekdays[activity.weekday[i]]++
    t.weeks[activity.week[i]]++
    t.categories[activity.category[i]]++
    if (isNight(activity.hour[i])) t.night++
    if (activity.source[i] === initiated) t.initiated++
    t.types.set(activity.type[i], (t.types.get(activity.type[i]) ?? 0) + 1)
    // A walk-in came to the station, so it has no time to arrive.
    if (activity.response[i] !== UNTIMED && activity.source[i] !== walkIn) {
      t.responses.push(activity.response[i])
    }
    if (activity.scene[i] !== UNTIMED) t.scenes.push(activity.scene[i])
  }
  return tallies
}

export const TOWN = 0
export const wholeTown = () => TOWN

// Groups entries by the card that shows them: a place listed on its street counts on the
// street's card, as its pin and headline do. `pins` is in activity's pin order.
export function cardGroupOf(activity: Activity, pins: Address[]): (entry: number) => number {
  const index = new Map(pins.map((pin, i) => [pin.id, i]))
  const card = pins.map((pin, i) =>
    pin.hidden && pin.street_id ? (index.get(pin.street_id) ?? i) : i,
  )
  return (entry) => card[activity.pin[entry]] ?? -1
}

// The middle value, or null when there are too few to trust.
export function typical(values: number[], least = MIN_TIMED): number | null {
  if (values.length < least) return null
  const sorted = [...values].sort((a, b) => a - b)
  return sorted[Math.floor(sorted.length / 2)]
}

// [lookup index, entries], most first, with ties in lookup order.
export function topOf(counts: Map<number, number>, limit: number): [number, number][] {
  return [...counts].sort((a, b) => b[1] - a[1] || a[0] - b[0]).slice(0, limit)
}
