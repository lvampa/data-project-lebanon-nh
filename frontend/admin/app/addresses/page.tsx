import { fetchAddresses } from '@/lib/api'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@project/ui/components/ui/table'
import { Badge } from '@project/ui/components/ui/badge'

export default async function AddressesPage() {
  const addresses = await fetchAddresses()

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Addresses</h1>
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
          {addresses.map((row) => (
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
    </div>
  )
}
