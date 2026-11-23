'use client'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { MapLegend } from '@project/ui/components/map/MapLegend'
import { IncidentMap, type Selection } from '@/components/incident-map'
import { PlaceSearch } from '@/components/police-map/place-search'
import type { FilteredCard } from '@/components/police-map/filtered-section'
import { SidePanel } from '@/components/police-map/side-panel'
import { streetPinOf } from '@/lib/police-map/approximate'
import { streetsToLight } from '@/lib/police-map/streets'
import { updatedLabel, windowLabel } from '@/lib/police-map/format'
import { idFromHash } from '@/lib/police-map/hash'
import { PIN_COLOR } from '@/lib/police-map/map-style'
import type { Address, StatsData } from '@/lib/types'

interface Props {
  // The year's rows. The selection, the hash and the search read these, so a filter change
  // never moves the map or re-runs the selection.
  addresses: Address[]
  stats: StatsData
  // While filters are on: the filtered rows the pins, the card and the summary count from.
  shown?: Address[]
  filtered?: FilteredCard | null
}

const NOTHING: Selection = { id: null, fly: false }

export function PoliceMap({ addresses, stats, shown, filtered = null }: Props) {
  const [selection, setSelection] = useState<Selection>(NOTHING)
  const yearPlaces = useMemo(() => new Map(addresses.map((a) => [a.id, a])), [addresses])
  const current = shown ?? addresses
  const places = useMemo(() => new Map(current.map((a) => [a.id, a])), [current])

  useEffect(() => {
    const read = () => {
      const id = idFromHash(window.location.hash, yearPlaces)
      setSelection(id ? { id, fly: true } : NOTHING)
    }
    read()
    window.addEventListener('hashchange', read)
    return () => window.removeEventListener('hashchange', read)
  }, [yearPlaces])

  const select = useCallback((id: string, fly: boolean) => {
    window.history.replaceState(null, '', `#${id}`)
    setSelection({ id, fly })
  }, [])

  const clear = useCallback(() => {
    window.history.replaceState(null, '', window.location.pathname + window.location.search)
    setSelection(NOTHING)
  }, [])

  const selected = selection.id ? places.get(selection.id) : undefined
  // A hidden place is somewhere on its street, so its street is lit and ringed.
  const streetPin = selected ? streetPinOf(selected, places) : undefined
  const streets = useMemo(() => {
    if (!selected) return []
    return streetsToLight(selected.hidden && streetPin ? streetPin : selected)
  }, [selected, streetPin])
  const ringed = selected ? (selected.hidden ? (selected.street_id ?? null) : selected.id) : null

  return (
    <div className="police-map-stage overflow-hidden rounded-lg border border-border bg-card">
      <div className="relative min-h-90">
        <IncidentMap
          addresses={current}
          selection={selection}
          ringed={ringed}
          streets={streets}
          onSelect={(id) => select(id, false)}
          noun={filtered?.noun}
        />
        <div className="absolute left-3.5 top-3.5 z-10 w-full max-w-80 pr-16">
          <PlaceSearch addresses={addresses} onChoose={(id) => select(id, true)} />
        </div>
        <div className="pointer-events-none absolute bottom-7 left-3.5 z-10">
          <MapLegend
            variant="scale"
            caption="Larger and darker means more activity"
            title={`Police activity · ${windowLabel(stats.since, stats.generated_at)}`}
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
          addresses={current}
          stats={stats}
          place={selected}
          onChoose={(id) => select(id, true)}
          onClose={clear}
          filtered={filtered}
        />
      </aside>
    </div>
  )
}
