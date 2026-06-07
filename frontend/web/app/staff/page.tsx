import { readDataFile } from '@/lib/data'
import { StaffTable } from '@/components/staff-table'
import type { StaffMember } from '@/lib/types'

export default function StaffPage() {
  const staff = readDataFile<StaffMember[]>('staff.json')
  const departments = [...new Set(staff.map(s => s.department))].sort()

  return (
    <div>
      <h1 className="text-2xl font-bold mb-2">City Staff</h1>
      <p className="text-sm text-muted-foreground mb-6">
        {staff.length} staff members · {departments.join(', ')}
      </p>
      <StaffTable staff={staff} />
    </div>
  )
}
