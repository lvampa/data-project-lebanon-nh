'use client'
import dynamic from 'next/dynamic'
import type { Address, StatsData } from '@/lib/types'

// MapLibre needs the browser, so the map is not prerendered.
const PoliceMap = dynamic(
  () => import('@/components/police-map/police-map').then((m) => m.PoliceMap),
  {
    ssr: false,
    loading: () => (
      <div className="police-map-stage place-items-center rounded-lg border text-sm text-muted-foreground">
        Loading the map…
      </div>
    ),
  },
)

interface Props {
  addresses: Address[]
  stats: StatsData
}

export function IncidentMapLoader({ addresses, stats }: Props) {
  return <PoliceMap addresses={addresses} stats={stats} />
}
