import type { TypeStat, WeekdayStat } from '@/lib/types'

const DAY_ORDER = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

export function formatTypeData(
  stats: TypeStat[],
  limit: number,
): { name: string; count: number }[] {
  return stats.slice(0, limit).map((s) => ({ name: s.incident_type, count: s.count }))
}

export function formatWeekdayData(stats: WeekdayStat[]): { day: string; count: number }[] {
  const byDay = new Map(stats.map((s) => [s.day, s.count]))
  return DAY_ORDER.map((day) => ({ day, count: byDay.get(day) ?? 0 }))
}
