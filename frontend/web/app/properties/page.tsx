import { Suspense } from 'react'
import { readDataFile } from '@/lib/data'
import { PropertySearch } from '@/components/property-search'
import type { PropertyRecord } from '@/lib/types'

export default function PropertiesPage() {
  const properties = readDataFile<PropertyRecord[]>('properties.json')

  return (
    <div>
      <h1 className="text-2xl font-bold mb-2">Properties</h1>
      <p className="text-sm text-muted-foreground mb-4">
        {properties.length.toLocaleString()} parcels · search by address or
        owner
      </p>
      <Suspense>
        <PropertySearch properties={properties} />
      </Suspense>
    </div>
  )
}
