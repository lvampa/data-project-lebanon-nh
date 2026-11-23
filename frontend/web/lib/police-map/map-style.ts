import type { ExpressionSpecification } from 'maplibre-gl'
import type { Address } from '../types'
import { hiddenCallsByStreet, isApproximatePlace } from './approximate'

export const PIN_COLOR = '#1f4e8c'
export const SELECTED_COLOR = '#a3195b'
// One busy place, such as the police station, would otherwise hide every other pin.
export const CALLS_CAP = 3000
export const CLUSTER_RADIUS = 38
export const CLUSTER_MAX_ZOOM = 15
// A group of places at one address opens no closer than street level.
export const GROUP_MAX_ZOOM = 17

// The box around a group's places, as [[west, south], [east, north]], for the camera to fit.
export function boundsOf(points: [number, number][]): [[number, number], [number, number]] {
  const lngs = points.map(([lng]) => lng)
  const lats = points.map(([, lat]) => lat)
  return [
    [Math.min(...lngs), Math.min(...lats)],
    [Math.max(...lngs), Math.max(...lats)],
  ]
}

// A click lands anywhere within this many pixels of a pin's center.
export const MIN_HIT_RADIUS = 20

// What a group of pins adds up: the calls its pins hold, and the weight that sizes it.
export const CLUSTER_PROPERTIES = {
  calls: ['+', ['+', ['get', 'n'], ['get', 'h']]],
  weight: ['+', ['get', 'w']],
}

export interface PinProperties {
  id: string
  name: string
  // Its own calls, which a group sums for "N calls".
  n: number
  // What sizes and shades it: its calls, or its traffic when it has no calls of its own.
  w: number
  // 1 for a place with no calls of its own, only traffic on its street.
  t: 0 | 1
  // 1 for a place whose point is only somewhere on its street.
  a: 0 | 1
  // The calls of the hidden places listed on this street, so a tooltip's "N calls" and a
  // group's total match the town's.
  h: number
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

// A place with no calls of its own, only traffic on its street, still matters on the map.
export function isTrafficOnly(address: Pick<Address, 'count' | 'traffic_count'>): boolean {
  return address.count === 0 && address.traffic_count > 0
}

// What sizes and shades a pin: its calls, or its traffic when it has no calls of its own.
export function pinCalls(address: Pick<Address, 'count' | 'traffic_count'>): number {
  return isTrafficOnly(address) ? address.traffic_count : address.count
}

// A place hidden under its street has no pin, so its calls ride on the street's pin: they add
// to its size (`w`), and to the "N calls" a tooltip or a group shows (`h`), so those match the
// town's totals. `n` stays the street's own count, which is what its card says.
export function pinsGeoJson(addresses: Address[]): PinCollection {
  const hiddenCalls = hiddenCallsByStreet(addresses)
  return {
    type: 'FeatureCollection',
    // A pin with nothing to show, such as one a filter emptied, is left off the map.
    features: addresses
      .filter((address) => !address.hidden)
      .filter((address) => pinCalls(address) + (hiddenCalls.get(address.id) ?? 0) > 0)
      .map((address) => ({
        type: 'Feature',
        properties: {
          id: address.id,
          name: pinName(address),
          n: address.count,
          w: pinCalls(address) + (hiddenCalls.get(address.id) ?? 0),
          t: isTrafficOnly(address) ? 1 : 0,
          a: isApproximatePlace(address) ? 1 : 0,
          h: hiddenCalls.get(address.id) ?? 0,
        },
        geometry: { type: 'Point', coordinates: [address.lng, address.lat] },
      })),
  }
}

// A single pin is sized by its weight, and a group of pins by the sum of theirs, so a group
// of traffic-only pins does not shrink to the minimum. Both are capped, and both are drawn
// as the same circle.
const calls: ExpressionSpecification = [
  'min',
  ['case', ['has', 'point_count'], ['get', 'weight'], ['get', 'w']],
  CALLS_CAP,
]

const baseRadius: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['sqrt', calls],
  ...[1, 7, 2, 8.5, 5, 12, 10, 17, 20, 25, 40, 36, 55, 46],
]

// A zoom expression may only be the input of a top-level interpolate, so every radius is
// one interpolate over zoom with its arithmetic inside each stop.
function radiusByZoom(
  stop: (radius: ExpressionSpecification) => ExpressionSpecification,
): ExpressionSpecification {
  return [
    'interpolate',
    ['linear'],
    ['zoom'],
    11,
    stop(['*', 0.8, baseRadius]),
    14,
    stop(baseRadius),
    17,
    stop(['*', 1.2, baseRadius]),
  ]
}

export const pinRadius = radiusByZoom((radius) => radius)

export const pinOpacity: ExpressionSpecification = [
  'interpolate',
  ['linear'],
  ['sqrt', calls],
  // .65 is the lowest that keeps a one-call pin at 3:1 on the light basemap.
  ...[1, 0.65, 3, 0.72, 6, 0.8, 15, 0.9],
]

export const sortByCalls: ExpressionSpecification = ['-', calls]

export const selectedRadius = radiusByZoom((radius) => ['+', 4, radius])

export const hitRadius = radiusByZoom((radius) => ['max', radius, MIN_HIT_RADIUS])
