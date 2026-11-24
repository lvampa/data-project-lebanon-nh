'use client'
import { DataStatus } from '@/components/data-status'
import { useDataFile } from '@/components/use-data-file'
import { PoliceViews } from '@/components/police-views/police-views'
import type { Address, StatsData } from '@/lib/types'

export default function PublicSafetyPage() {
  const addresses = useDataFile<Address[]>('addresses.json')
  const stats = useDataFile<StatsData>('stats.json')
  if (addresses.status !== 'ready' || stats.status !== 'ready') {
    return <DataStatus states={[addresses, stats]} />
  }
  return <PoliceViews addresses={addresses.data} stats={stats.data} />
}
