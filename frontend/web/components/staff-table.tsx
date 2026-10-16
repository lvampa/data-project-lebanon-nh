import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@project/ui/components/ui/table'
import { Badge } from '@project/ui/components/ui/badge'
import type { StaffMember } from '@/lib/types'

const DEPT_VARIANT: Record<string, 'default' | 'secondary' | 'outline'> = {
  Police: 'default',
  Fire: 'secondary',
}

interface Props {
  staff: StaffMember[]
}

export function StaffTable({ staff }: Props) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Name</TableHead>
          <TableHead>Title</TableHead>
          <TableHead>Department</TableHead>
          <TableHead>Division</TableHead>
          <TableHead>Email</TableHead>
          <TableHead>Phone</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {staff.map((person) => (
          <TableRow key={person.id}>
            <TableCell className="font-medium">{person.name}</TableCell>
            <TableCell className="text-sm text-muted-foreground">{person.title ?? '—'}</TableCell>
            <TableCell>
              <Badge variant={DEPT_VARIANT[person.department] ?? 'outline'}>
                {person.department}
              </Badge>
            </TableCell>
            <TableCell className="text-sm">{person.division ?? '—'}</TableCell>
            <TableCell className="text-sm">
              {person.email ? (
                <a href={`mailto:${person.email}`} className="text-blue-600 hover:underline">
                  {person.email}
                </a>
              ) : (
                '—'
              )}
            </TableCell>
            <TableCell className="text-sm">{person.phone ?? '—'}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
