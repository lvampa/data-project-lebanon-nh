'use client'
import { useMemo } from 'react'
import type { FilteredCard } from '@/components/police-map/filtered-section'
import { ReportCard } from '@/components/police-map/report-card'
import { TownSummary } from '@/components/police-map/town-summary'
import { usePlaceCard } from '@/components/police-map/use-place-card'
import { placesOnStreet, rankCounts, streetNameOf } from '@/lib/police-map/approximate'
import type { Address, StatsData } from '@/lib/types'

interface Props {
  addresses: Address[]
  stats: StatsData
  place: Address | undefined
  onChoose: (id: string) => void
  onClose: () => void
  filtered?: FilteredCard | null
}

// The panel beside the map: the report card of the selected place, or the town as a whole.
export function SidePanel({ addresses, stats, place, onChoose, onClose, filtered = null }: Props) {
  const { state, retry } = usePlaceCard(place?.id ?? null)
  const kind = place?.kind
  const places = useMemo(() => new Map(addresses.map((a) => [a.id, a])), [addresses])
  const counts = useMemo(() => (kind ? rankCounts(addresses, kind) : []), [addresses, kind])

  if (!place || !state) {
    return (
      <TownSummary
        addresses={addresses}
        stats={stats}
        onChoose={onChoose}
        noun={filtered?.noun}
        filtered={filtered !== null}
      />
    )
  }
  return (
    <ReportCard
      key={place.id}
      address={place}
      streetLabel={streetNameOf(place, places)}
      onStreet={place.kind === 'road' ? placesOnStreet(addresses, place.id) : []}
      onChoose={onChoose}
      state={state}
      counts={counts}
      year={stats.since.slice(0, 4)}
      since={stats.since}
      onClose={onClose}
      onRetry={retry}
      filtered={filtered}
    />
  )
}
