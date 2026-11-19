'use client'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { MapLegend } from '@project/ui/components/map/MapLegend'
import { IncidentMap, type Selection } from '@/components/incident-map'
import { PlaceSearch } from '@/components/police-map/place-search'
import { SidePanel } from '@/components/police-map/side-panel'
import { streetsToLight } from '@/lib/police-map/streets'
import { updatedLabel, windowLabel } from '@/lib/police-map/format'
import { idFromHash } from '@/lib/police-map/hash'
import { PIN_COLOR } from '@/lib/police-map/map-style'
import type { Address, StatsData } from '@/lib/types'

interface Props {
  addresses: Address[]
  stats: StatsData
}

const NOTHING: Selection = { id: null, fly: false }

export function PoliceMap({ addresses, stats }: Props) {
  const [selection, setSelection] = useState<Selection>(NOTHING)
  const places = useMemo(() => new Map(addresses.map((a) => [a.id, a])), [addresses])

  useEffect(() => {
    const read = () => {
      const id = idFromHash(window.location.hash, places)
      setSelection(id ? { id, fly: true } : NOTHING)
    }
    read()
    window.addEventListener('hashchange', read)
    return () => window.removeEventListener('hashchange', read)
  }, [places])

  const select = useCallback((id: string, fly: boolean) => {
    window.history.replaceState(null, '', `#${id}`)
    setSelection({ id, fly })
  }, [])

  const clear = useCallback(() => {
    window.history.replaceState(null, '', window.location.pathname + window.location.search)
    setSelection(NOTHING)
  }, [])

  const selected = selection.id ? places.get(selection.id) : undefined
  const streets = useMemo(() => (selected ? streetsToLight(selected) : []), [selected])

  return (
    <div className="police-map-stage overflow-hidden rounded-lg border border-border bg-card">
      <div className="relative min-h-90">
        <IncidentMap
          addresses={addresses}
          selection={selection}
          streets={streets}
          onSelect={(id) => select(id, false)}
        />
        <div className="absolute left-3.5 top-3.5 z-10 w-full max-w-80 pr-16">
          <PlaceSearch addresses={addresses} onChoose={(id) => select(id, true)} />
        </div>
        <div className="pointer-events-none absolute bottom-7 left-3.5 z-10">
          <MapLegend
            variant="scale"
            title={`Police calls · ${windowLabel(stats.since, stats.generated_at)}`}
            lastUpdated={updatedLabel(stats.generated_at)}
            color={PIN_COLOR}
          />
        </div>
      </div>
      <aside
        className="overflow-y-auto border-t border-border p-5 lg:border-l lg:border-t-0"
        aria-live="polite"
      >
        <SidePanel
          addresses={addresses}
          stats={stats}
          place={selected}
          onChoose={(id) => select(id, true)}
          onClose={clear}
        />
      </aside>
    </div>
  )
}
