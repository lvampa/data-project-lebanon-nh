import { readDataFile } from '@/lib/data'
import { PoliceViews } from '@/components/police-views/police-views'
import type { Address, StatsData } from '@/lib/types'

export default function MapPage() {
  const addresses = readDataFile<Address[]>('addresses.json')
  const stats = readDataFile<StatsData>('stats.json')
  return <PoliceViews addresses={addresses} stats={stats} />
}
