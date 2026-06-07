'use client'
import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { addressToMarker } from '@/lib/map-utils'
import type { Address } from '@/lib/types'

const LEBANON_CENTER: [number, number] = [-72.252, 43.642]

interface Props {
  addresses: Address[]
}

export function IncidentMap({ addresses }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? 'https://tiles.openfreemap.org/styles/liberty',
      center: LEBANON_CENTER,
      zoom: 13,
    })

    map.addControl(new maplibregl.NavigationControl(), 'top-right')

    map.on('load', () => {
      addresses.forEach(addr => {
        const { lngLat, label } = addressToMarker(addr)
        new maplibregl.Marker({ color: '#3b82f6' })
          .setLngLat(lngLat)
          .setPopup(new maplibregl.Popup({ offset: 25 }).setHTML(label))
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
