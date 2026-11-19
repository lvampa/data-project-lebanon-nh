'use client'
import { useEffect, useRef } from 'react'
import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { addressToMarker } from '@/lib/map-utils'
import type { Address } from '@/lib/types'
import { LEBANON_CENTER, LEBANON_ZOOM } from '@project/ui/lib/constants'

interface Props {
  addresses: Address[]
}

export function IncidentMap({ addresses }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current) return

    // MapLibre 6 finds its worker next to its own script, which breaks once Next bundles
    // it. This lets the bundler emit the worker and hand MapLibre the real URL.
    maplibregl.setWorkerUrl(
      new URL('maplibre-gl/dist/maplibre-gl-worker.mjs', import.meta.url).href,
    )

    const map = new maplibregl.Map({
      container: containerRef.current,
      style:
        process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? 'https://tiles.openfreemap.org/styles/liberty',
      center: LEBANON_CENTER,
      zoom: LEBANON_ZOOM,
    })

    map.addControl(new maplibregl.NavigationControl(), 'top-right')

    map.on('load', () => {
      addresses.forEach((addr) => {
        const { lngLat, popup } = addressToMarker(addr)
        new maplibregl.Marker({ color: '#3b82f6' })
          .setLngLat(lngLat)
          .setPopup(new maplibregl.Popup({ offset: 25 }).setDOMContent(popup))
          .addTo(map)
      })
    })

    return () => map.remove()
  }, [addresses])

  return (
    <div
      ref={containerRef}
      className="w-full rounded-lg overflow-hidden border"
      style={{ height: '600px' }}
    />
  )
}
