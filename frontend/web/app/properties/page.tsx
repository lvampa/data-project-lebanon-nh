'use client'
import { Suspense } from 'react'
import { DATA_FILES } from '@/lib/data'
import { DataStatus } from '@/components/data-status'
import { useDataFile } from '@/components/use-data-file'
import { PropertySearch } from '@/components/property-search'
import type { PropertyRecord } from '@/lib/types'

export default function PropertiesPage() {
  const propertiesFile = useDataFile<PropertyRecord[]>(DATA_FILES.properties)
  if (propertiesFile.status !== 'ready') return <DataStatus states={[propertiesFile]} />

  const properties = propertiesFile.data

  return (
    <div>
      <h1 className="text-2xl font-bold mb-2">Properties</h1>
      <p className="text-sm text-muted-foreground mb-4">
        {properties.length.toLocaleString()} parcels · search by address or owner
      </p>
      <Suspense>
        <PropertySearch properties={properties} />
      </Suspense>
    </div>
  )
}
