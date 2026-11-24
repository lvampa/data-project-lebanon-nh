'use client'
import { Suspense } from 'react'
import { DATA_FILES } from '@/lib/data'
import { DataStatus } from '@/components/data-status'
import { useDataFile } from '@/components/use-data-file'
import { IncidentsFilters } from '@/components/incidents-filters'
import { IncidentsTable } from '@/components/incidents-table'
import type { Incident } from '@/lib/types'

export default function IncidentsPage() {
  const incidentsFile = useDataFile<Incident[]>(DATA_FILES.incidents)
  if (incidentsFile.status !== 'ready') return <DataStatus states={[incidentsFile]} />

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Incidents</h1>
      <Suspense>
        <IncidentsFilters />
        <IncidentsTable incidents={incidentsFile.data} />
      </Suspense>
    </div>
  )
}
