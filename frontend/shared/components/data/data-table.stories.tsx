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
  { id: 'case_number', header: 'Case #', sortable: true },
  { id: 'reported_at', header: 'Date', sortable: true },
  { id: 'incident_type', header: 'Type', sortable: true },
  { id: 'officer', header: 'Officer', sortable: true },
  { id: 'disposition', header: 'Disposition' },
]

export const Default: StoryObj = {
  render: () => <DataTable columns={COLUMNS} rows={INCIDENTS} rowKey={(r) => r.case_number} />,
}

export const Compact: StoryObj = {
  render: () => <DataTable columns={COLUMNS} rows={INCIDENTS} density="compact" rowKey={(r) => r.case_number} />,
}

export const Unborderd: StoryObj = {
  render: () => <DataTable columns={COLUMNS} rows={INCIDENTS} bordered={false} rowKey={(r) => r.case_number} />,
}

export const WithCaption: StoryObj = {
  render: () => (
    <DataTable
      columns={COLUMNS}
      rows={INCIDENTS}
      rowKey={(r) => r.case_number}
      caption="Source: Lebanon Police Department CAD export · Provisional · Updated daily"
    />
  ),
}

export const Clickable: StoryObj = {
  render: () => (
    <DataTable
      columns={COLUMNS}
      rows={INCIDENTS}
      rowKey={(r) => r.case_number}
      onRowClick={(row) => alert(`Selected: ${row.case_number}`)}
    />
  ),
}

export const Empty: StoryObj = {
  render: () => (
    <DataTable columns={COLUMNS} rows={[]} empty="No incidents match the current filters." />
  ),
}

const BUDGET = [
  { indicator: 'Operating budget', fy24: '$61.4M', fy23: '$58.9M', change: '+4.2%' },
  { indicator: 'Mill rate',         fy24: '$18.32', fy23: '$17.91', change: '+2.3%' },
  { indicator: 'SAU88 enrollment',  fy24: '3,402',  fy23: '3,466',  change: '−1.8%' },
  { indicator: 'Building permits',  fy24: '284',    fy23: '261',    change: '+8.8%' },
]

export const MunicipalData: StoryObj = {
  render: () => (
    <DataTable
      columns={[
        { id: 'indicator', header: 'Indicator', sortable: true },
        { id: 'fy24', header: 'FY24', numeric: true },
        { id: 'fy23', header: 'FY23', numeric: true },
        { id: 'change', header: 'Change', numeric: true },
      ]}
      rows={BUDGET}
      caption="Lebanon, NH · FY23–24 · Source: City of Lebanon annual report"
    />
  ),
}
