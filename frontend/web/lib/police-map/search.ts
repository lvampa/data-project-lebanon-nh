import type { Address } from '../types'
import { isTrafficOnly, pinCalls, pinName } from './map-style'
import { DIRECTION, SUFFIX } from './streets'

const MIN_QUERY = 2

// One spelling per word, so "Mt" finds "Mount", "road" finds "Rd" and "north" finds "N".
const SHORT_FORM: Record<string, string> = {
  mount: 'mt',
  ...Object.fromEntries(
    Object.entries({ ...SUFFIX, ...DIRECTION }).map(([short, long]) => [
      long.toLowerCase(),
      short.toLowerCase(),
    ]),
  ),
}

function searchForm(text: string): string {
  return text
    .toLowerCase()
    .replace(/[.,]/g, '')
    .split(/\s+/)
    .filter((word) => word !== '')
    .map((word) => SHORT_FORM[word] ?? word)
    .join(' ')
}

// The number beside a result: its calls, or "62 traffic" for a place with only traffic.
export function resultCount(address: Address): string {
  const n = pinCalls(address).toLocaleString('en-US')
  return isTrafficOnly(address) ? `${n} traffic` : n
}

// Places and streets whose name holds what was typed, busiest first.
// The text as typed matches anywhere, and the one spelling per word matches where a word
// starts, since "west" folds to "w", which is in every other name.
export function searchPlaces(addresses: Address[], query: string, limit = 8): Address[] {
  const typed = query.trim().toLowerCase()
  if (typed.length < MIN_QUERY) return []
  const folded = ` ${searchForm(query)}`
  const matches = (name: string) =>
    name.toLowerCase().includes(typed) || ` ${searchForm(name)}`.includes(folded)
  return addresses
    .filter((address) => matches(pinName(address)))
    .sort((a, b) => pinCalls(b) - pinCalls(a) || pinName(a).localeCompare(pinName(b)))
    .slice(0, limit)
}
