'use client'
import { useState } from 'react'
import { ReportCard } from '@/components/police-map/report-card'
import { usePlaceCard } from '@/components/police-map/use-place-card'
import type { Address } from '@/lib/types'

interface Props {
  place: Address | undefined
  counts: number[]
  year: string
  onClose: () => void
}

// The panel beside the map: the report card of the selected place.
export function SidePanel({ place, counts, year, onClose }: Props) {
  const [attempt, setAttempt] = useState(0)
  const state = usePlaceCard(place?.id ?? null, attempt)

  if (!place || !state) {
    return <p className="text-sm text-muted-foreground">Click a pin to see what happens there.</p>
  }
  return (
    <ReportCard
      key={place.id}
      address={place}
      state={state}
      counts={counts}
      year={year}
      onClose={onClose}
      onRetry={() => setAttempt((n) => n + 1)}
    />
  )
}
