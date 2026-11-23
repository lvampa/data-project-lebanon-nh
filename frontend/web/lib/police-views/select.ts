import type { Address } from '@/lib/types'
import { CATEGORY_KEYS, type Activity } from './activity'
import { KINDS, inTimeOfDay, rangeDays, type Filters } from './filters'

// The log files reports taken at the station under the station, not where they happened,
// so it would top any count of calls about a place.
export const STATION_ID = 'lebanon-police-department-poverty-ln'

// What a view counts. `all` is every entry, for the map, busy times and officers.
// `public` is calls from the public about something at a place, for Places: an incident at
// a place, started by a caller, never road traffic, an officer's own check or the station.
export type Lens = 'all' | 'public'

// The last day the log covers, which the date ranges count back from.
export function lastDayOf(activity: Activity): number {
  let last = 0
  for (let i = 0; i < activity.size; i++) if (activity.day[i] > last) last = activity.day[i]
  return last
}

// 1 for each entry the filters keep, in entry order.
export function selectEntries(
  activity: Activity,
  addresses: Address[],
  filters: Filters,
  lens: Lens,
): Uint8Array {
  const kept = new Uint8Array(activity.size)
  const firstDay = lastDayOf(activity) - rangeDays(filters.range) + 1
  const kindCategory = KINDS.find((kind) => kind.id === filters.kind)!.category
  const onlyCategory = kindCategory === null ? -1 : CATEGORY_KEYS.indexOf(kindCategory)
  // An officer no entry names keeps nothing, rather than everything.
  const officer = filters.officer === null ? -1 : activity.officers.indexOf(filters.officer)
  const premises = CATEGORY_KEYS.indexOf('premises')
  const initiated = activity.sources.indexOf('Initiated')
  const station = addresses.findIndex((address) => address.id === STATION_ID)

  for (let i = 0; i < activity.size; i++) {
    if (activity.day[i] < firstDay) continue
    if (!inTimeOfDay(activity.hour[i], filters.time)) continue
    if (filters.officer !== null && activity.officer[i] !== officer) continue
    if (lens === 'public') {
      const pin = activity.pin[i]
      if (activity.category[i] !== premises) continue
      if (activity.source[i] === initiated) continue
      if (addresses[pin].kind !== 'place' || pin === station) continue
    } else if (onlyCategory >= 0 && activity.category[i] !== onlyCategory) {
      continue
    }
    kept[i] = 1
  }
  return kept
}
