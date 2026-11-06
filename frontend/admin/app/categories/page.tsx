import { fetchCategories } from '@/lib/api'
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

export default async function CategoriesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>
}) {
  const params = await searchParams
  const data = await fetchCategories({ page: pageFromParams(params.page), per_page: PER_PAGE })

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Categories ({data.total.toLocaleString()})</h1>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Incident Type</TableHead>
            <TableHead>Category</TableHead>
            <TableHead>Subcategory</TableHead>
            <TableHead>Count</TableHead>
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {data.items.map((row) => (
            <TableRow key={row.raw_incident_type}>
              <TableCell>{row.raw_incident_type}</TableCell>
              <TableCell>{row.category ?? '—'}</TableCell>
              <TableCell>{row.subcategory ?? '—'}</TableCell>
              <TableCell>{row.count}</TableCell>
              <TableCell>
                <Badge variant={row.is_categorized ? 'default' : 'outline'}>
                  {row.is_categorized ? 'categorized' : 'pending'}
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
