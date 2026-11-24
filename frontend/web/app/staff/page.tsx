'use client'
import { DataStatus } from '@/components/data-status'
import { useDataFile } from '@/components/use-data-file'
import { StaffTable } from '@/components/staff-table'
import type { StaffMember } from '@/lib/types'

export default function StaffPage() {
  const staffFile = useDataFile<StaffMember[]>('staff.json')
  if (staffFile.status !== 'ready') return <DataStatus states={[staffFile]} />

  const staff = staffFile.data
  const departments = [...new Set(staff.map((s) => s.department))].sort()

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
