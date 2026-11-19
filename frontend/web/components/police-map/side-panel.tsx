'use client'
import { useMemo, useState } from 'react'
import { ReportCard } from '@/components/police-map/report-card'
import { TownSummary } from '@/components/police-map/town-summary'
import { usePlaceCard } from '@/components/police-map/use-place-card'
import type { Address, StatsData } from '@/lib/types'

interface Props {
  addresses: Address[]
  stats: StatsData
  place: Address | undefined
  onChoose: (id: string) => void
  onClose: () => void
}

// The panel beside the map: the report card of the selected place, or the town as a whole.
export function SidePanel({ addresses, stats, place, onChoose, onClose }: Props) {
  const [attempt, setAttempt] = useState(0)
  const state = usePlaceCard(place?.id ?? null, attempt)
  const counts = useMemo(() => addresses.map((a) => a.count), [addresses])

  if (!place || !state) {
    return <TownSummary addresses={addresses} stats={stats} onChoose={onChoose} />
  }
  return (
    <ReportCard
      key={place.id}
      address={place}
      state={state}
      counts={counts}
      year={stats.since.slice(0, 4)}
      onClose={onClose}
      onRetry={() => setAttempt((n) => n + 1)}
    />
  )
}
