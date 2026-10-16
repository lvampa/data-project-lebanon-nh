'use client'
import { useMemo, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@project/ui/components/ui/table'
import { Badge } from '@project/ui/components/ui/badge'
import { Pagination } from '@project/ui/components/data/pagination'
import type { Incident } from '@/lib/types'
import { PER_PAGE } from '@project/ui/lib/constants'

interface Props {
  incidents: Incident[]
}

export function IncidentsTable({ incidents }: Props) {
  const searchParams = useSearchParams()
  const incidentType = searchParams.get('incident_type')
  const officer = searchParams.get('officer')

  const filterKey = `${incidentType}|${officer}`
  const [pageForFilter, setPageForFilter] = useState({ filterKey, page: 1 })
  const page = pageForFilter.filterKey === filterKey ? pageForFilter.page : 1
  const setPage = (page: number) => setPageForFilter({ filterKey, page })

  const filtered = useMemo(() => {
    return incidents.filter((r) => {
      if (
        incidentType &&
        !(r.incident_type ?? '').toLowerCase().includes(incidentType.toLowerCase())
      )
        return false
      if (officer && !(r.officer ?? '').toLowerCase().includes(officer.toLowerCase())) return false
      return true
    })
  }, [incidents, incidentType, officer])

  const totalPages = Math.max(1, Math.ceil(filtered.length / PER_PAGE))
  const slice = filtered.slice((page - 1) * PER_PAGE, page * PER_PAGE)

  return (
    <div>
      <p className="text-sm text-muted-foreground mb-2">
        {filtered.length.toLocaleString()} incidents
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Date</TableHead>
            <TableHead>Case #</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Disposition</TableHead>
            <TableHead>Location</TableHead>
            <TableHead>Officer</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {slice.map((row, i) => (
            <TableRow key={row.case_number ?? i}>
              <TableCell className="text-xs tabular-nums whitespace-nowrap">
                {row.reported_at?.slice(0, 16).replace('T', ' ') ?? '—'}
              </TableCell>
              <TableCell className="text-xs">
                {row.source_url ? (
                  <Link href={row.source_url} target="_blank" className="underline">
                    {row.case_number ?? '—'}
                  </Link>
                ) : (
                  (row.case_number ?? '—')
                )}
              </TableCell>
              <TableCell>
                {row.incident_type && (
                  <Badge variant="secondary" className="text-xs">
                    {row.incident_type}
                  </Badge>
                )}
              </TableCell>
              <TableCell className="text-xs">{row.disposition ?? '—'}</TableCell>
              <TableCell className="text-xs">{row.location ?? '—'}</TableCell>
              <TableCell className="text-xs">{row.officer ?? '—'}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
    </div>
  )
}
