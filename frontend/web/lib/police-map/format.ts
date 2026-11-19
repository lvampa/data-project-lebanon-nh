const NEW_HAMPSHIRE = 'America/New_York'
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function callWord(count: number): string {
  return `${count.toLocaleString('en-US')} ${count === 1 ? 'call' : 'calls'}`
}

// "Lebanon Ford" from "Lebanon Ford, 90 Miracle Mile".
export function nameOf(name: string): string {
  return name.split(', ')[0]
}

// "90 Miracle Mile" from "Lebanon Ford, 90 Miracle Mile", and null for a road.
export function streetOf(name: string): string | null {
  const rest = name.split(', ').slice(1).join(', ')
  return rest === '' ? null : rest
}

function inNewHampshire(iso: string, options: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat('en-US', { timeZone: NEW_HAMPSHIRE, ...options }).format(
    new Date(iso),
  )
}

// "Jan to Nov 2026" for a window that starts in January 2026 and was generated in November.
export function windowLabel(since: string, generatedAt: string): string {
  const [year, month] = since.split('-').map(Number)
  const start = MONTHS[month - 1]
  const endYear = Number(inNewHampshire(generatedAt, { year: 'numeric' }))
  const end = inNewHampshire(generatedAt, { month: 'short' })
  if (endYear === year) return start === end ? `${start} ${year}` : `${start} to ${end} ${year}`
  return `${start} ${year} to ${end} ${endYear}`
}

// "Nov 19, 2026"
export function updatedLabel(generatedAt: string): string {
  return inNewHampshire(generatedAt, { month: 'short', day: 'numeric', year: 'numeric' })
}
