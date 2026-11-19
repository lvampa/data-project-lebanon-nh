import type { Address } from '../types'
import { isTrafficOnly, pinCalls, pinName } from './map-style'

const MIN_QUERY = 2

// The number beside a result: its calls, or "62 traffic" for a place with only traffic.
export function resultCount(address: Address): string {
  const n = pinCalls(address).toLocaleString('en-US')
  return isTrafficOnly(address) ? `${n} traffic` : n
}

// Places and streets whose name holds what was typed, busiest first.
export function searchPlaces(addresses: Address[], query: string, limit = 8): Address[] {
  const needle = query.trim().toLowerCase()
  if (needle.length < MIN_QUERY) return []
  return addresses
    .filter((address) => pinName(address).toLowerCase().includes(needle))
    .sort((a, b) => pinCalls(b) - pinCalls(a) || pinName(a).localeCompare(pinName(b)))
    .slice(0, limit)
}
