import type { Address } from '../types'
import { pinName } from './map-style'

const MIN_QUERY = 2

// Places and streets whose name holds what was typed, busiest first.
export function searchPlaces(addresses: Address[], query: string, limit = 8): Address[] {
  const needle = query.trim().toLowerCase()
  if (needle.length < MIN_QUERY) return []
  return addresses
    .filter((address) => pinName(address).toLowerCase().includes(needle))
    .sort((a, b) => b.count - a.count || pinName(a).localeCompare(pinName(b)))
    .slice(0, limit)
}
