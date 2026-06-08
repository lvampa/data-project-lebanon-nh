import type { Meta, StoryObj } from '@storybook/react-vite'
import { DataTable } from './data-table'

const meta: Meta = {
  title: 'Data/DataTable',
  parameters: { layout: 'padded' },
}
export default meta

const INCIDENTS = [
  { case_number: '26-14755', reported_at: '2026-05-13', incident_type: 'Business Check', officer: 'Benjamin Begin', disposition: 'Log Information' },
  { case_number: '26-14753', reported_at: '2026-05-13', incident_type: 'Directed Patrol', officer: 'Sergeant James Pike', disposition: 'Log Information' },
  { case_number: '26-14752', reported_at: '2026-05-13', incident_type: 'Business Check', officer: 'Cpl. Jodi Dumayne', disposition: 'Log Information' },
  { case_number: '26-14751', reported_at: '2026-05-13', incident_type: '911 Abandoned Call', officer: 'Sergeant James Pike', disposition: null },
  { case_number: '26-14750', reported_at: '2026-05-13', incident_type: 'Directed Patrol', officer: 'Benjamin Begin', disposition: 'Log Information' },
]

const COLUMNS = [
  { key: 'case_number', header: 'Case #', sortable: true },
  { key: 'reported_at', header: 'Date', sortable: true },
  { key: 'incident_type', header: 'Type', sortable: true },
  { key: 'officer', header: 'Officer', sortable: true },
  { key: 'disposition', header: 'Disposition' },
]

export const Default: StoryObj = {
  render: () => <DataTable columns={COLUMNS} data={INCIDENTS} />,
}

export const Compact: StoryObj = {
  render: () => <DataTable columns={COLUMNS} data={INCIDENTS} density="compact" />,
}

export const Clickable: StoryObj = {
  render: () => (
    <DataTable
      columns={COLUMNS}
      data={INCIDENTS}
      onRowClick={(row) => alert(`Selected: ${row.case_number}`)}
    />
  ),
}

export const Empty: StoryObj = {
  render: () => (
    <DataTable columns={COLUMNS} data={[]} emptyMessage="No incidents match the current filters." />
  ),
}

const BUDGET = [
  { indicator: 'Operating budget', fy24: '$61.4M', fy23: '$58.9M', change: '+4.2%' },
  { indicator: 'Mill rate', fy24: '$18.32', fy23: '$17.91', change: '+2.3%' },
  { indicator: 'SAU88 enrollment', fy24: '3,402', fy23: '3,466', change: '−1.8%' },
  { indicator: 'Building permits', fy24: '284', fy23: '261', change: '+8.8%' },
]

export const MunicipalData: StoryObj = {
  render: () => (
    <DataTable
      columns={[
        { key: 'indicator', header: 'Indicator', sortable: true },
        { key: 'fy24', header: 'FY24', numeric: true },
        { key: 'fy23', header: 'FY23', numeric: true },
        { key: 'change', header: 'Change', numeric: true },
      ]}
      data={BUDGET}
    />
  ),
}
