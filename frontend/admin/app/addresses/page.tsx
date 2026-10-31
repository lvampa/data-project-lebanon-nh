import { fetchAddresses } from '@/lib/api'
import { pageFromParams } from '@/lib/paging'
import { PER_PAGE } from '@project/ui/lib/constants'
import { PageNav } from '@/components/page-nav'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@project/ui/components/ui/table'
import { Badge } from '@project/ui/components/ui/badge'

export default async function AddressesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>
}) {
  const params = await searchParams
  const data = await fetchAddresses({ page: pageFromParams(params.page), per_page: PER_PAGE })

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Addresses ({data.total.toLocaleString()})</h1>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Raw Address</TableHead>
            <TableHead>Normalized</TableHead>
            <TableHead>Lat</TableHead>
            <TableHead>Lng</TableHead>
            <TableHead>Count</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.items.map((row) => (
            <TableRow key={row.raw_address}>
              <TableCell>{row.raw_address}</TableCell>
              <TableCell>{row.normalized_address ?? '—'}</TableCell>
              <TableCell>{row.lat ?? '—'}</TableCell>
              <TableCell>{row.lng ?? '—'}</TableCell>
              <TableCell>{row.count}</TableCell>
              <TableCell>
                <Badge variant={row.is_normalized ? 'default' : 'outline'}>
                  {row.is_normalized ? 'normalized' : 'pending'}
                </Badge>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <PageNav page={data.page} total={data.total} perPage={data.per_page} />
    </div>
  )
}
