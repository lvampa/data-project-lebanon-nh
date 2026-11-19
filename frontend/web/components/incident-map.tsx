'use client'
import { useEffect, useMemo, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { MapControls } from '@project/ui/components/map/MapControls'
import { MapErrorState } from '@project/ui/components/map/MapErrorState'
import { MapLoadingState } from '@project/ui/components/map/MapLoadingState'
import { LEBANON_CENTER, LEBANON_ZOOM } from '@project/ui/lib/constants'
import { callWord, clusterHolds, nameOf, trafficNearby } from '@/lib/police-map/format'
import { NO_PIN, pinLayers, streetLayer } from '@/lib/police-map/layers'
import {
  CLUSTER_MAX_ZOOM,
  CLUSTER_PROPERTIES,
  CLUSTER_RADIUS,
  pinsGeoJson,
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
        clusterProperties: CLUSTER_PROPERTIES,
      })

      // A style without the tiles' road names has no street to light.
      if (map.getSource('openmaptiles')) map.addLayer(streetLayer('openmaptiles'))
      pinLayers('pins').forEach((layer) => map.addLayer(layer))

      const tip = new maplibregl.Popup({
        closeButton: false,
        closeOnClick: false,
        className: 'map-tip',
        offset: 10,
      })
      // On every move, so the tip follows the pin under the cursor when pins overlap.
      map.on('mousemove', 'hit', (event) => {
        map.getCanvas().style.cursor = 'pointer'
        const feature = event.features?.[0]
        if (!feature || feature.geometry.type !== 'Point') return
        const props = feature.properties as {
          name?: string
          n?: number
          point_count?: number
          calls?: number
          t?: number
          w?: number
          weight?: number
        }
        const label = document.createElement('div')
        const strong = document.createElement('strong')
        if (props.point_count) {
          strong.textContent = `${props.point_count} places`
          label.append(
            strong,
            ` · ${clusterHolds(props.calls ?? 0, props.weight ?? 0)} · zoom in to see them`,
          )
        } else {
          strong.textContent = nameOf(props.name ?? '')
          label.append(
            strong,
            ` · ${props.t ? trafficNearby(props.w ?? 0) : callWord(props.n ?? 0)}`,
          )
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
