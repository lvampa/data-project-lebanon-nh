import type { Address } from '../types'
import { hiddenCallsByStreet } from './approximate'
import { isTrafficOnly, pinName, pinTotal } from './map-style'
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
    .map((word) => (isShortened(word) ? SHORT_FORM[word] : word))
    .join(' ')
}

// Own keys only, so a word like "constructor" is not read off the object's prototype.
function isShortened(word: string): boolean {
  return Object.hasOwn(SHORT_FORM, word)
}

// The number beside a result, the same as its pin and card: a street with its places, or
// "62 traffic" for a place with only traffic.
export function resultCount(address: Address, hidden: Map<string, number>): string {
  const n = pinTotal(address, hidden).toLocaleString('en-US')
  return isTrafficOnly(address) ? `${n} traffic` : n
}

// Places and streets whose name holds what was typed, busiest first.
// The text as typed matches anywhere, and the one spelling per word matches where a word
// starts, since "west" folds to "w", which is in every other name. A word that was
// shortened was typed in full, so it must end there too, or "south" finds every "St".
export function searchPlaces(addresses: Address[], query: string, limit = 8): Address[] {
  const typed = query.trim().toLowerCase()
  if (typed.length < MIN_QUERY) return []
  const lastWord = typed.replace(/[.,]/g, '').split(/\s+/).at(-1) ?? ''
  const folded = ` ${searchForm(query)}${isShortened(lastWord) ? ' ' : ''}`
  const matches = (name: string) =>
    name.toLowerCase().includes(typed) || ` ${searchForm(name)} `.includes(folded)
  const hidden = hiddenCallsByStreet(addresses)
  return (
    addresses
      // A pin with nothing to count is off the map, so it is not a result either.
      .filter((address) => pinTotal(address, hidden) > 0 && matches(pinName(address)))
      .sort(
        (a, b) => pinTotal(b, hidden) - pinTotal(a, hidden) || pinName(a).localeCompare(pinName(b)),
      )
      .slice(0, limit)
  )
}
