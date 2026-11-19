import type { LayerSpecification } from 'maplibre-gl'
import {
  PIN_COLOR,
  SELECTED_COLOR,
  hitRadius,
  pinOpacity,
  pinRadius,
  selectedRadius,
  sortByCalls,
} from './map-style'
import { streetFilter } from './streets'

export const NO_PIN = ''

// Under the pins, so a lit street never covers a circle.
export function streetLayer(source: string): LayerSpecification {
  return {
    id: 'street',
    type: 'line',
    source,
    'source-layer': 'transportation_name',
    filter: streetFilter([]),
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color': SELECTED_COLOR,
      'line-width': ['interpolate', ['linear'], ['zoom'], 12, 4, 16, 8],
      'line-opacity': 0.35,
    },
  }
}

// One kind of circle, for a place and for a group of places alike. Its size and opacity
// follow the calls it holds.
export function pinLayers(source: string): LayerSpecification[] {
  return [
    {
      id: 'pins',
      type: 'circle',
      source,
      layout: { 'circle-sort-key': sortByCalls },
      paint: {
        'circle-radius': pinRadius,
        'circle-color': PIN_COLOR,
        'circle-opacity': pinOpacity,
        'circle-blur': 0.28,
      },
    },
    {
      id: 'selected',
      type: 'circle',
      source,
      filter: ['==', ['get', 'id'], NO_PIN],
      paint: {
        'circle-radius': selectedRadius,
        'circle-color': 'rgba(0,0,0,0)',
        'circle-stroke-color': SELECTED_COLOR,
        'circle-stroke-width': 2.5,
      },
    },
    {
      id: 'hit',
      type: 'circle',
      source,
      paint: { 'circle-radius': hitRadius, 'circle-opacity': 0 },
    },
  ]
}
