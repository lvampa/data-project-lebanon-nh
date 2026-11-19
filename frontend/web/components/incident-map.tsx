'use client'
import { useEffect, useMemo, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { MapControls } from '@project/ui/components/map/MapControls'
import { MapErrorState } from '@project/ui/components/map/MapErrorState'
import { MapLoadingState } from '@project/ui/components/map/MapLoadingState'
import { LEBANON_CENTER, LEBANON_ZOOM } from '@project/ui/lib/constants'
import { callWord, nameOf } from '@/lib/police-map/format'
import {
  CLUSTER_MAX_ZOOM,
  CLUSTER_RADIUS,
  PIN_COLOR,
  SELECTED_COLOR,
  hitRadius,
  pinOpacity,
  pinRadius,
  pinsGeoJson,
  selectedRadius,
  sortByCalls,
} from '@/lib/police-map/map-style'
import { streetFilter } from '@/lib/police-map/streets'
import type { Address } from '@/lib/types'

export interface Selection {
  id: string | null
  // Fly to the place, as a search result or a list click does. A click on the pin does not.
  fly: boolean
}

interface Props {
  addresses: Address[]
  selection: Selection
  // Streets to light up, spelled as the map tiles spell them. None lights nothing.
  streets: string[]
  onSelect: (id: string) => void
}

type Status = 'loading' | 'ready' | 'error'

const NO_PIN = ''

export function IncidentMap({ addresses, selection, streets, onSelect }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const onSelectRef = useRef(onSelect)
  const [status, setStatus] = useState<Status>('loading')
  const [attempt, setAttempt] = useState(0)
  const places = useMemo(() => new Map(addresses.map((a) => [a.id, a])), [addresses])

  useEffect(() => {
    onSelectRef.current = onSelect
  })

  useEffect(() => {
    if (!containerRef.current) return

    // MapLibre 6 finds its worker next to its own script, which breaks once Next bundles
    // it. This lets the bundler emit the worker and hand MapLibre the real URL.
    maplibregl.setWorkerUrl(
      new URL('maplibre-gl/dist/maplibre-gl-worker.mjs', import.meta.url).href,
    )

    setStatus('loading')
    const map = new maplibregl.Map({
      container: containerRef.current,
      style:
        process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? 'https://tiles.openfreemap.org/styles/positron',
      center: LEBANON_CENTER,
      zoom: LEBANON_ZOOM,
    })
    mapRef.current = map

    map.on('error', () => {
      // A failed tile is not fatal. Only a map that never loaded is.
      if (!map.loaded()) setStatus((current) => (current === 'ready' ? current : 'error'))
    })

    map.on('load', () => {
      map.addSource('pins', {
        type: 'geojson',
        data: pinsGeoJson(addresses),
        cluster: true,
        clusterRadius: CLUSTER_RADIUS,
        clusterMaxZoom: CLUSTER_MAX_ZOOM,
        clusterProperties: { calls: ['+', ['get', 'n']] },
      })

      // Under the pins, so a lit street never covers a circle. A style without the
      // tiles' road names simply has nothing to light.
      if (map.getSource('openmaptiles')) {
        map.addLayer({
          id: 'street',
          type: 'line',
          source: 'openmaptiles',
          'source-layer': 'transportation_name',
          filter: streetFilter([]),
          layout: { 'line-cap': 'round', 'line-join': 'round' },
          paint: {
            'line-color': SELECTED_COLOR,
            'line-width': ['interpolate', ['linear'], ['zoom'], 12, 4, 16, 8],
            'line-opacity': 0.35,
          },
        })
      }

      // One kind of circle, for a place and for a group of places alike. Its size and
      // opacity follow the calls it holds.
      map.addLayer({
        id: 'pins',
        type: 'circle',
        source: 'pins',
        layout: { 'circle-sort-key': sortByCalls },
        paint: {
          'circle-radius': pinRadius,
          'circle-color': PIN_COLOR,
          'circle-opacity': pinOpacity,
          'circle-blur': 0.28,
        },
      })
      map.addLayer({
        id: 'selected',
        type: 'circle',
        source: 'pins',
        filter: ['==', ['get', 'id'], NO_PIN],
        paint: {
          'circle-radius': selectedRadius,
          'circle-color': 'rgba(0,0,0,0)',
          'circle-stroke-color': SELECTED_COLOR,
          'circle-stroke-width': 2.5,
        },
      })
      map.addLayer({
        id: 'hit',
        type: 'circle',
        source: 'pins',
        paint: { 'circle-radius': hitRadius, 'circle-opacity': 0 },
      })

      const tip = new maplibregl.Popup({
        closeButton: false,
        closeOnClick: false,
        className: 'map-tip',
        offset: 10,
      })
      map.on('mouseenter', 'hit', (event) => {
        map.getCanvas().style.cursor = 'pointer'
        const feature = event.features?.[0]
        if (!feature || feature.geometry.type !== 'Point') return
        const props = feature.properties as {
          name?: string
          n?: number
          point_count?: number
          calls?: number
        }
        const label = document.createElement('div')
        const strong = document.createElement('strong')
        if (props.point_count) {
          strong.textContent = `${props.point_count} places`
          label.append(strong, ` · ${callWord(props.calls ?? 0)} · click to zoom in`)
        } else {
          strong.textContent = nameOf(props.name ?? '')
          label.append(strong, ` · ${callWord(props.n ?? 0)}`)
        }
        tip
          .setLngLat(feature.geometry.coordinates as [number, number])
          .setDOMContent(label)
          .addTo(map)
      })
      map.on('mouseleave', 'hit', () => {
        map.getCanvas().style.cursor = ''
        tip.remove()
      })
      map.on('click', 'hit', async (event) => {
        const feature = event.features?.[0]
        if (!feature || feature.geometry.type !== 'Point') return
        const props = feature.properties as { id?: string; cluster_id?: number }
        if (props.cluster_id === undefined) {
          if (props.id) onSelectRef.current(props.id)
          return
        }
        // A group opens by zooming in until its places separate.
        const source = map.getSource('pins') as maplibregl.GeoJSONSource
        const zoom = await source.getClusterExpansionZoom(props.cluster_id)
        map.easeTo({ center: feature.geometry.coordinates as [number, number], zoom: zoom + 0.3 })
      })

      setStatus('ready')
    })

    return () => {
      mapRef.current = null
      map.remove()
    }
  }, [addresses, attempt])

  // The selected pin gets a ring, and a place chosen from a list or a search is flown to.
  useEffect(() => {
    const map = mapRef.current
    if (!map || status !== 'ready') return
    map.setFilter('selected', ['==', ['get', 'id'], selection.id ?? NO_PIN])
    if (map.getLayer('street')) map.setFilter('street', streetFilter(streets))
    const place = selection.id ? places.get(selection.id) : undefined
    if (place && selection.fly) {
      map.flyTo({
        center: [place.lng, place.lat],
        zoom: Math.max(map.getZoom(), 16),
        duration: 600,
      })
    }
  }, [selection, streets, status, places])

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="absolute inset-0" />
      {status === 'loading' && (
        <div className="absolute inset-0">
          <MapLoadingState progress="Loading the map" />
        </div>
      )}
      {status === 'error' && (
        <div className="absolute inset-0">
          <MapErrorState
            title="The map did not load"
            message="The map tiles could not be reached. Check your connection and try again."
            onRetry={() => setAttempt((n) => n + 1)}
          />
        </div>
      )}
      {status === 'ready' && (
        <div className="absolute right-3.5 top-3.5">
          <MapControls
            onZoomIn={() => mapRef.current?.zoomIn()}
            onZoomOut={() => mapRef.current?.zoomOut()}
            onRecenter={() => mapRef.current?.flyTo({ center: LEBANON_CENTER, zoom: LEBANON_ZOOM })}
          />
        </div>
      )}
    </div>
  )
}
