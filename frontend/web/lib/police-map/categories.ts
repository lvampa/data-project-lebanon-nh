// The kinds of call a place's card counts, in the order the bar draws them. The color is a
// chart token, always in this order, and a kind keeps its color wherever it appears.
export const CATEGORIES = [
  { key: 'premises', label: 'At the place', color: 'var(--chart-1)' },
  { key: 'traffic', label: 'Traffic', color: 'var(--chart-2)' },
  { key: 'alarms', label: 'Alarms', color: 'var(--chart-3)' },
  { key: 'checks', label: 'Police checks and patrols', color: 'var(--chart-4)' },
  { key: 'admin', label: 'Paperwork', color: 'var(--chart-5)' },
] as const

export type CategoryKey = (typeof CATEGORIES)[number]['key']

export type CategoryCounts = Record<CategoryKey, number>

const BY_KEY = Object.fromEntries(CATEGORIES.map((c) => [c.key, c])) as Record<
  CategoryKey,
  (typeof CATEGORIES)[number]
>

export function categoryOf(key: string) {
  return BY_KEY[key as CategoryKey] ?? BY_KEY.premises
}

// A place's calls leave road traffic out, because it happened on the road. A road keeps it.
export function categoriesFor(kind: 'place' | 'road', counts: CategoryCounts) {
  return CATEGORIES.filter((c) => (kind === 'road' || c.key !== 'traffic') && counts[c.key] > 0)
}
