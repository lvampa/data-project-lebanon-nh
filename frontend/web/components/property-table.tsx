import Link from 'next/link'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@project/ui/components/ui/table'
import { Badge } from '@project/ui/components/ui/badge'
import type { PropertyRecord } from '@/lib/types'

interface Props {
  properties: PropertyRecord[]
}

export function PropertyTable({ properties }: Props) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Address</TableHead>
          <TableHead>Owner</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Assessed</TableHead>
          <TableHead>Built</TableHead>
          <TableHead>Sqft</TableHead>
          <TableHead></TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {properties.map((p) => (
          <TableRow key={p.parcel_id}>
            <TableCell className="font-medium text-sm">{p.location ?? '—'}</TableCell>
            <TableCell className="text-sm">{p.owner ?? '—'}</TableCell>
            <TableCell className="text-xs">
              {p.land_use && (
                <Badge variant="outline" className="text-xs">
                  {p.land_use}
                </Badge>
              )}
            </TableCell>
            <TableCell className="text-sm tabular-nums">
              {p.assessed_total != null ? `$${p.assessed_total.toLocaleString()}` : '—'}
            </TableCell>
            <TableCell className="text-sm">{p.year_built ?? '—'}</TableCell>
            <TableCell className="text-sm tabular-nums">
              {p.building_sqft != null ? p.building_sqft.toLocaleString() : '—'}
            </TableCell>
            <TableCell>
              {p.detail_url && (
                <Link
                  href={p.detail_url}
                  target="_blank"
                  aria-label={`View VGSI record for ${p.location ?? p.parcel_id}`}
                  className="text-xs text-blue-600 hover:underline"
                >
                  VGSI →
                </Link>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
