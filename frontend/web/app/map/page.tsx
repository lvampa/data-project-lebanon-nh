import { readDataFile } from '@/lib/data'
import { IncidentMapLoader } from '@/components/incident-map-loader'
import type { Address, StatsData } from '@/lib/types'

export default function MapPage() {
  const addresses = readDataFile<Address[]>('addresses.json')
  const stats = readDataFile<StatsData>('stats.json')

  return (
    <div>
      <h1 className="sr-only">Police calls map</h1>
      <IncidentMapLoader addresses={addresses} stats={stats} />
    </div>
  )
}
