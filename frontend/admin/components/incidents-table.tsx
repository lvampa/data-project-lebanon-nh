import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@project/ui/components/ui/table'
import type { IncidentsResponse } from '@/lib/types'

export function IncidentsTable({ data }: { data: IncidentsResponse }) {
  return (
    <div>
      <p className="text-sm text-muted-foreground mb-2">
        {data.total.toLocaleString()} results — page {data.page}
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Date/Time</TableHead>
            <TableHead>Case #</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Disposition</TableHead>
            <TableHead>Location</TableHead>
            <TableHead>Officer</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.items.map((row, i) => (
            <TableRow key={row.case_number ?? i}>
              <TableCell>{row.reported_at ?? '—'}</TableCell>
              <TableCell>{row.case_number ?? '—'}</TableCell>
              <TableCell>{row.incident_type ?? '—'}</TableCell>
              <TableCell>{row.disposition ?? '—'}</TableCell>
              <TableCell>{row.location ?? '—'}</TableCell>
              <TableCell>{row.officer ?? '—'}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
