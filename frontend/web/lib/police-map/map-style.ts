import type { ExpressionSpecification } from 'maplibre-gl'
import type { Address } from '../types'

export const PIN_COLOR = '#1f4e8c'
export const SELECTED_COLOR = '#a3195b'
// One busy place, such as the police station, would otherwise hide every other pin.
export const CALLS_CAP = 3000
export const CLUSTER_RADIUS = 38
export const CLUSTER_MAX_ZOOM = 15
// A click lands anywhere within this many pixels of a pin's center.
export const MIN_HIT_RADIUS = 20

export interface PinProperties {
  id: string
  name: string
  n: number
}

export interface PinFeature {
  type: 'Feature'
  properties: PinProperties
  geometry: { type: 'Point'; coordinates: [number, number] }
}

export interface PinCollection {
  type: 'FeatureCollection'
  features: PinFeature[]
}

export function pinName(address: Pick<Address, 'normalized_address' | 'raw_address'>): string {
  return address.normalized_address ?? address.raw_address
}

export function pinsGeoJson(addresses: Address[]): PinCollection {
  return {
    type: 'FeatureCollection',
    features: addresses.map((address) => ({
      type: 'Feature',
      properties: { id: address.id, name: pinName(address), n: address.count },
      geometry: { type: 'Point', coordinates: [address.lng, address.lat] },
    })),
  }
}

// A single pin holds `n` calls, and a group of pins holds the sum of theirs. Both are
// capped, and both are drawn as the same circle.
const calls: ExpressionSpecification = [
  'min',
  ['case', ['has', 'point_count'], ['get', 'calls'], ['get', 'n']],
  CALLS_CAP,
]

const baseRadius: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['sqrt', calls],
  ...[1, 7, 2, 8.5, 5, 12, 10, 17, 20, 25, 40, 36, 55, 46],
]

export const pinRadius: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['zoom'],
  11,
  ['*', 0.8, baseRadius],
  14,
  baseRadius,
  17,
  ['*', 1.2, baseRadius],
]

export const pinOpacity: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['sqrt', calls],
  ...[1, 0.45, 3, 0.62, 6, 0.78, 15, 0.9],
]

export const sortByCalls: ExpressionSpecification = ['-', calls]

export const selectedRadius: ExpressionSpecification = ['+', 4, pinRadius]

export const hitRadius: ExpressionSpecification = ['max', pinRadius, MIN_HIT_RADIUS]
