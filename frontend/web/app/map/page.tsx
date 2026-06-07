import { readDataFile } from '@/lib/data'
import { IncidentMapLoader } from '@/components/incident-map-loader'
import type { Address } from '@/lib/types'

export default function MapPage() {
  const addresses = readDataFile<Address[]>('addresses.json')

  return (
    <div>
      <h1 className="text-2xl font-bold mb-2">Incident Map</h1>
      <p className="text-sm text-muted-foreground mb-4">
        {addresses.length} geocoded locations · click a marker for details
      </p>
      <IncidentMapLoader addresses={addresses} />
    </div>
  )
}
