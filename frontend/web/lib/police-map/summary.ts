import type { Address, HourStat, WeekdayStat } from '../types'
import { hiddenCallsByStreet } from './approximate'
import { pinName, pinTotal } from './map-style'

const DAY_NAMES: Record<string, string> = {
  Sun: 'Sunday',
  Mon: 'Monday',
  Tue: 'Tuesday',
  Wed: 'Wednesday',
  Thu: 'Thursday',
  Fri: 'Friday',
  Sat: 'Saturday',
}

export function hourLabel(hour: number): string {
  if (hour === 0) return '12 am'
  if (hour === 12) return 'noon'
  return hour < 12 ? `${hour} am` : `${hour - 12} pm`
}

function busiest<T extends { count: number }>(rows: T[]): T | null {
  return rows.reduce<T | null>(
    (top, row) => (top === null || row.count > top.count ? row : top),
    null,
  )
}

// The weekday with the most calls, spelled out: "Friday".
export function busiestDay(byWeekday: WeekdayStat[]): string | null {
  const top = busiest(byWeekday)
  return top ? (DAY_NAMES[top.day] ?? top.day) : null
}

// The hour of the day with the most calls: "4 pm".
export function busiestHour(byHour: HourStat[]): string | null {
  const top = busiest(byHour)
  return top ? hourLabel(top.hour) : null
}

// The places with the most calls, busiest first, on the same footing as a place card's rank.
// A place listed on its street is in here too; the streets list is a separate list.
export function busiestPlaces(addresses: Address[], limit: number): Address[] {
  return addresses
    .filter((a) => a.kind === 'place')
    .sort((a, b) => b.count - a.count)
    .slice(0, limit)
}

// The streets with the most activity, each with the total its pin and card show. A crossing
// is two streets, so it is not a street of its own here.
export function busiestStreets(
  addresses: Address[],
  limit: number,
): { address: Address; total: number }[] {
  const hidden = hiddenCallsByStreet(addresses)
  return addresses
    .filter((a) => a.kind === 'road' && !pinName(a).includes(' and '))
    .map((address) => ({ address, total: pinTotal(address, hidden) }))
    .sort((a, b) => b.total - a.total)
    .slice(0, limit)
}

// Every entry with a spot on the map, once: a road's count holds its traffic, and a place's
// traffic is counted apart from its calls.
export function mappedTotal(addresses: Address[]): number {
  return addresses.reduce((sum, a) => sum + a.count + (a.kind === 'place' ? a.traffic_count : 0), 0)
}
