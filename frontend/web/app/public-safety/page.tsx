'use client'
import { DATA_FILES } from '@/lib/data'
import { DataStatus } from '@/components/data-status'
import { useDataFile } from '@/components/use-data-file'
import { PoliceViews } from '@/components/police-views/police-views'
import type { Address, StatsData } from '@/lib/types'

export default function PublicSafetyPage() {
  const addresses = useDataFile<Address[]>(DATA_FILES.addresses)
  const stats = useDataFile<StatsData>(DATA_FILES.stats)
  if (addresses.status !== 'ready' || stats.status !== 'ready') {
    return <DataStatus states={[addresses, stats]} />
  }
  return <PoliceViews addresses={addresses.data} stats={stats.data} />
}
