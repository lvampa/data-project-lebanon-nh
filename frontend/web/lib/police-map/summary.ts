import type { Address, HourStat, WeekdayStat } from '../types'

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

// The places with the most calls, busiest first.
export function busiestPlaces(addresses: Address[], limit: number): Address[] {
  return [...addresses].sort((a, b) => b.count - a.count).slice(0, limit)
}
