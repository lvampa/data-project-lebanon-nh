import { createExpression } from '@maplibre/maplibre-gl-style-spec'
import { describe, expect, it } from 'vitest'
import { CLUSTER_PROPERTIES, pinsGeoJson } from '@/lib/police-map/map-style'
import type { Address } from '@/lib/types'

// MapLibre reads each clusterProperties entry as exactly [operator, mapExpression] and
// ignores anything after those two. An entry like ['+', a, b] keeps only `a`, silently.
describe('CLUSTER_PROPERTIES', () => {
  it.each(Object.entries(CLUSTER_PROPERTIES))(
    '%s is exactly [operator, expression]',
    (_name, entry) => {
      expect(entry).toHaveLength(2)
      expect(typeof entry[0]).toBe('string')
      expect(Array.isArray(entry[1])).toBe(true)
    },
  )
})

// What the map does with the entries, the way supercluster does: the map expression runs on
// each pin, and the operator folds the results over the pins of a group.
function foldCluster(
  name: keyof typeof CLUSTER_PROPERTIES,
  pins: Record<string, unknown>[],
): number {
  const [operator, mapExpression] = CLUSTER_PROPERTIES[name]
  const parsed = createExpression(mapExpression, 'cluster', {
    type: 'number',
    'property-type': 'data-driven',
    expression: { interpolated: false, parameters: ['zoom', 'feature'] },
  } as never)
  if (parsed.result !== 'success') throw new Error('the map expression does not parse')
  const mapped = pins.map(
    (properties) =>
      parsed.value.evaluate({ zoom: 0 } as never, { type: 'Point', properties } as never) as number,
  )
  expect(operator).toBe('+')
  return mapped.reduce((sum, value) => sum + value, 0)
}

function pin(id: string, count: number, extra: Partial<Address> = {}): Address {
  return {
    id,
    kind: 'place',
    raw_address: id,
    normalized_address: id,
    count,
    traffic_count: 0,
    lat: 43.674,
    lng: -72.2656,
    precision: 'exact',
    street_id: null,
    hidden: false,
    ...extra,
  }
}

describe('a group of pins, folded the way the map folds it', () => {
  const addresses = [
    pin('street', 600, { kind: 'road' }),
    pin('quarry', 900, { street_id: 'street', hidden: true, precision: 'approximate' }),
    pin('marek', 120, { street_id: 'street', hidden: true, precision: 'approximate' }),
    pin('ford', 400),
  ]
  const drawn = pinsGeoJson(addresses).features.map((f) => ({ ...f.properties }))

  it('holds every call, hidden places included, so it matches the town total', () => {
    expect(foldCluster('calls', drawn)).toBe(2020)
  })

  it('is sized by the weight of its pins', () => {
    expect(foldCluster('weight', drawn)).toBe(600 + 900 + 120 + 400)
  })
})
