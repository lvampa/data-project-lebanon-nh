import type { WeekFlag } from '@/lib/police-views/findings'

// "Mar 26", the first day of a week. Weeks count from `since`, the first day published.
export function weekStart(since: string, week: number): string {
  const start = new Date(`${since}T00:00:00Z`).getTime()
  return new Date(start + week * 7 * 86_400_000).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  })
}

export function weekNote(flag: WeekFlag): string | null {
  if (flag === 'thin') return 'Some logs for this week are missing.'
  if (flag === 'partial') return 'This week so far.'
  return null
}
