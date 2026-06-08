import { Suspense } from 'react'
import { fetchIncidents } from '@/lib/api'
import { PER_PAGE } from '@project/ui/lib/constants'
import { IncidentsFilters } from '@/components/incidents-filters'
import { IncidentsTable } from '@/components/incidents-table'

export default async function IncidentsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>
}) {
  const params = await searchParams
  const data = await fetchIncidents({
    date_from: params.date_from,
    date_to: params.date_to,
    incident_type: params.incident_type,
    officer: params.officer,
    page: params.page ? parseInt(params.page) : 1,
    per_page: PER_PAGE,
  })

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Incidents</h1>
      <Suspense>
        <IncidentsFilters />
      </Suspense>
      <IncidentsTable data={data} />
    </div>
  )
}
