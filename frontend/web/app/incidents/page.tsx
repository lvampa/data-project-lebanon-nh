import { Suspense } from 'react'
import { readDataFile } from '@/lib/data'
import { IncidentsFilters } from '@/components/incidents-filters'
import { IncidentsTable } from '@/components/incidents-table'
import type { Incident } from '@/lib/types'

export default function IncidentsPage() {
  const incidents = readDataFile<Incident[]>('incidents.json')

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Incidents</h1>
      <Suspense>
        <IncidentsFilters />
        <IncidentsTable incidents={incidents} />
      </Suspense>
    </div>
  )
}
