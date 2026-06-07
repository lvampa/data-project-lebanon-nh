import type { Address } from '@/lib/types'

export interface MarkerConfig {
  lngLat: [number, number]
  label: string
  count: number
}

export function addressToMarker(address: Address): MarkerConfig {
  const displayName = address.normalized_address ?? address.raw_address
  const plural = address.count === 1 ? 'incident' : 'incidents'
  return {
    lngLat: [address.lng, address.lat],
    label: `<strong>${displayName}</strong><br>${address.count} ${plural}`,
    count: address.count,
  }
}
