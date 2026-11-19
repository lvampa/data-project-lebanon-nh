import { validateStyleMin } from '@maplibre/maplibre-gl-style-spec'
import { describe, expect, it } from 'vitest'
import { NO_PIN, pinLayers, streetLayer } from '@/lib/police-map/layers'
import { CLUSTER_MAX_ZOOM, CLUSTER_RADIUS } from '@/lib/police-map/map-style'

// The map refuses a layer the style spec rejects, and then nothing on it works. So every
// layer the page adds is checked here, in a minimal style that has its sources.
function styleWith(layers: ReturnType<typeof pinLayers>) {
  return {
    version: 8 as const,
    sources: {
      pins: {
        type: 'geojson' as const,
        data: { type: 'FeatureCollection' as const, features: [] },
        cluster: true,
        clusterRadius: CLUSTER_RADIUS,
        clusterMaxZoom: CLUSTER_MAX_ZOOM,
        clusterProperties: { calls: ['+', ['get', 'n']] },
      },
      openmaptiles: { type: 'vector' as const, url: 'https://example.com/tiles.json' },
    },
    layers,
  }
}

function errorsOf(layers: ReturnType<typeof pinLayers>) {
  return validateStyleMin(styleWith(layers) as never).map((e) => e.message)
}

describe('the police map layers', () => {
  it.each(pinLayers('pins').map((layer) => [layer.id, layer] as const))(
    'the %s layer passes the style spec',
    (_id, layer) => {
      expect(errorsOf([layer])).toEqual([])
    },
  )

  it('the street layer passes the style spec', () => {
    expect(errorsOf([streetLayer('openmaptiles')])).toEqual([])
  })

  it('all the layers together pass', () => {
    expect(errorsOf([streetLayer('openmaptiles'), ...pinLayers('pins')])).toEqual([])
  })

  it('starts with no pin selected', () => {
    const selected = pinLayers('pins').find((layer) => layer.id === 'selected')
    expect(selected && 'filter' in selected ? selected.filter : null).toEqual([
      '==',
      ['get', 'id'],
      NO_PIN,
    ])
  })
})
