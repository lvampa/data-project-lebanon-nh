import type { Address } from '../types'
import { nameOf, streetOf } from './format'

// The address as the map names it, which map-style also says, kept here so the two files
// do not import each other.
function nameFor(address: Pick<Address, 'normalized_address' | 'raw_address'>): string {
  return address.normalized_address ?? address.raw_address
}

// A place whose point is only somewhere on its street.
export function isApproximatePlace(address: Pick<Address, 'kind' | 'precision'>): boolean {
  return address.kind === 'place' && address.precision === 'approximate'
}

// The calls of the hidden places on each street, keyed by the street pin's id.
export function hiddenCallsByStreet(addresses: Address[]): Map<string, number> {
  const calls = new Map<string, number>()
  for (const address of addresses) {
    if (address.hidden && address.street_id) {
      calls.set(address.street_id, (calls.get(address.street_id) ?? 0) + address.count)
    }
  }
  return calls
}

// The places listed on a street's card, busiest first.
export function placesOnStreet(addresses: Address[], streetId: string): Address[] {
  return addresses
    .filter((a) => a.hidden && a.street_id === streetId)
    .sort((a, b) => b.count - a.count || nameFor(a).localeCompare(nameFor(b)))
}

// The street pin a hidden place is listed on.
export function streetPinOf(
  address: Pick<Address, 'street_id'>,
  places: Map<string, Address>,
): Address | undefined {
  return address.street_id ? places.get(address.street_id) : undefined
}

// The street an approximate place is somewhere on: its street pin's name, or the street part
// of its own address with the house number dropped.
export function streetNameOf(address: Address, places: Map<string, Address>): string | null {
  const road = streetPinOf(address, places)
  if (road) return nameOf(nameFor(road))
  const street = streetOf(nameFor(address))
  return street ? street.replace(/^\d+[A-Za-z]?(-\d+)?\s+/, '') : null
}
