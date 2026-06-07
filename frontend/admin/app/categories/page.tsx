import { fetchCategories } from '@/lib/api'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@project/ui/components/ui/table'
import { Badge } from '@project/ui/components/ui/badge'

export default async function CategoriesPage() {
  const categories = await fetchCategories()

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Categories</h1>
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
          {categories.map((row) => (
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
    </div>
  )
}
