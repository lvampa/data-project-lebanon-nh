import React from 'react'
import type { Meta, StoryObj } from '@storybook/react-vite'
import { DataTable, type DataTableColumn } from './data-table'
import { Sparkline } from './sparkline'
import { Badge } from '../ui/badge'

const meta: Meta = {
  title: 'Data/DataTable',
  parameters: { layout: 'padded' },
}
export default meta

// ─── Helpers ────────────────────────────────────────────────────────────────

function Delta({ value, invert = false }: { value: number; invert?: boolean }) {
  const positive = value >= 0
  const good = invert ? !positive : positive
  return (
    <span
      className="inline-flex items-center gap-0.5 font-mono tabular-nums text-[12px] font-medium"
      style={{ color: good ? 'var(--success)' : 'var(--destructive)' }}
    >
      {positive ? '▲' : '▼'} {Math.abs(value).toFixed(1)}%
    </span>
  )
}

function StatusBadge({ status }: { status: string }) {
  const variant =
    status === 'Verified'    ? 'secondary' :
    status === 'Provisional' ? 'destructive' :
    status === 'Updated'     ? 'outline' : 'secondary'
  return <Badge variant={variant} className="text-[11px]">{status}</Badge>
}

// ─── Dataset ────────────────────────────────────────────────────────────────

type Indicator = {
  code: string
  name: string
  sector: string
  value: number
  unit: string
  yoy: number
  invertPolarity: boolean
  trend: number[]
  status: string
}

const INDICATORS: Indicator[] = [
  { code: 'POP.TOT',   name: 'Total population',          sector: 'Demographics', value: 13151,  unit: 'people',   yoy: 0.4,  invertPolarity: false, trend: [12568,12700,12815,12932,13020,13085,13110,13151], status: 'Verified' },
  { code: 'FIN.BUD',   name: 'Operating budget',          sector: 'Finance',      value: 61.4,   unit: 'M USD',    yoy: 4.2,  invertPolarity: false, trend: [48.2,50.1,52.6,54.9,56.8,58.4,59.0,61.4],         status: 'Verified' },
  { code: 'FIN.MILL',  name: 'Mill rate, municipal',       sector: 'Finance',      value: 8.12,   unit: '$/1k',     yoy: -0.4, invertPolarity: true,  trend: [9.05,8.91,8.74,8.58,8.42,8.31,8.20,8.12],         status: 'Verified' },
  { code: 'EDU.ENR',   name: 'SAU88 total enrollment',    sector: 'Schools',      value: 1672,   unit: 'students', yoy: -1.8, invertPolarity: true,  trend: [1740,1735,1720,1710,1700,1690,1680,1672],           status: 'Verified' },
  { code: 'EDU.PPE',   name: 'Per-pupil expenditure',     sector: 'Schools',      value: 22140,  unit: 'USD',      yoy: 5.2,  invertPolarity: false, trend: [16200,17400,18600,19500,20100,20800,21200,22140],   status: 'Verified' },
  { code: 'PLAN.PRMT', name: 'Building permits issued',   sector: 'Planning',     value: 284,    unit: 'count',    yoy: 12.6, invertPolarity: false, trend: [180,205,222,238,250,260,272,284],                   status: 'Verified' },
  { code: 'PLAN.VAL',  name: 'Median assessed value, SFH', sector: 'Planning',   value: 412000, unit: 'USD',      yoy: 7.4,  invertPolarity: false, trend: [285000,310000,335000,358000,378000,392000,400000,412000], status: 'Provisional' },
  { code: 'LAB.UE',    name: 'Unemployment rate, LMA',    sector: 'Labor',        value: 2.1,    unit: '%',        yoy: -0.2, invertPolarity: true,  trend: [2.8,2.7,2.6,2.5,2.4,2.3,2.2,2.1],                 status: 'Verified' },
  { code: 'ENV.RIV',   name: 'Mascoma River nitrate',     sector: 'Environment',  value: 0.84,   unit: 'mg/L',     yoy: -2.3, invertPolarity: true,  trend: [1.10,1.04,0.98,0.95,0.92,0.89,0.86,0.84],          status: 'Provisional' },
]

function fmt(v: number) {
  return v >= 1000 ? v.toLocaleString() : String(v)
}

const INDICATOR_COLUMNS: DataTableColumn<Indicator>[] = [
  {
    id: 'code',
    header: 'Code',
    width: 110,
    sortable: true,
    accessor: (r) => (
      <code className="font-mono text-[12px] text-muted-foreground">{r.code}</code>
    ),
  },
  {
    id: 'name',
    header: 'Indicator',
    sortable: true,
    accessor: (r) => <span className="font-medium">{r.name}</span>,
  },
  {
    id: 'sector',
    header: 'Sector',
    width: 120,
    sortable: true,
    accessor: (r) => (
      <Badge variant="outline" className="text-[11px] font-normal">{r.sector}</Badge>
    ),
  },
  {
    id: 'value',
    header: 'Latest',
    width: 130,
    numeric: true,
    sortable: true,
    sortBy: (r) => r.value,
    accessor: (r) => (
      <span>
        <strong className="font-mono tabular-nums">{fmt(r.value)}</strong>{' '}
        <span className="text-[11px] text-muted-foreground">{r.unit}</span>
      </span>
    ),
  },
  {
    id: 'yoy',
    header: 'YoY',
    width: 90,
    numeric: true,
    sortable: true,
    sortBy: (r) => (r.invertPolarity ? -r.yoy : r.yoy),
    accessor: (r) => <Delta value={r.yoy} invert={r.invertPolarity} />,
  },
  {
    id: 'trend',
    header: 'Trend (8y)',
    width: 140,
    accessor: (r) => (
      <Sparkline
        values={r.trend}
        width={120}
        height={26}
        color="var(--foreground)"
      />
    ),
  },
  {
    id: 'status',
    header: 'Status',
    width: 110,
    sortable: true,
    accessor: (r) => <StatusBadge status={r.status} />,
  },
]

// ─── Stories ────────────────────────────────────────────────────────────────

/** Full indicators table — demonstrates all column features: sortable, numeric,
 *  sortBy extractor, accessor renderer, fixed widths, delta colors, sparklines,
 *  and status badges. */
export const Indicators: StoryObj = {
  render: () => (
    <DataTable
      columns={INDICATOR_COLUMNS}
      rows={INDICATORS}
      rowKey={(r) => r.code}
      caption="Lebanon, NH · Municipal & regional indicators · Source: LDP v3.2"
    />
  ),
}

export const IndicatorsCompact: StoryObj = {
  render: () => (
    <DataTable
      columns={INDICATOR_COLUMNS}
      rows={INDICATORS}
      rowKey={(r) => r.code}
      density="compact"
    />
  ),
}

/** Each column prop demonstrated explicitly. */
export const AllColumnOptions: StoryObj = {
  render: () => {
    type Row = { id: string; label: string; count: number; change: number; note: string | null }
    const rows: Row[] = [
      { id: 'A', label: 'Police',     count: 151,  change:  3.2,  note: 'Verified' },
      { id: 'B', label: 'Fire',       count: 38,   change: -1.4,  note: 'Provisional' },
      { id: 'C', label: 'Medical',    count: 214,  change:  8.7,  note: 'Verified' },
      { id: 'D', label: 'Traffic',    count: 96,   change: -0.5,  note: null },
    ]
    const cols: DataTableColumn<Row>[] = [
      // plain text, sortable
      { id: 'id',     header: 'ID',     width: 60,  sortable: true },
      // accessor — custom render
      { id: 'label',  header: 'Category', sortable: true,
        accessor: (r) => <span className="font-medium">{r.label}</span> },
      // numeric — right-aligned mono tabular-nums
      { id: 'count',  header: 'Count',  width: 80,  numeric: true, sortable: true },
      // sortBy — sort by raw number even though display is formatted
      { id: 'change', header: 'Change', width: 100, numeric: true, sortable: true,
        sortBy: (r) => r.change,
        accessor: (r) => <Delta value={r.change} /> },
      // accessor + nullable
      { id: 'note',   header: 'Status', width: 120,
        accessor: (r) => r.note ? <StatusBadge status={r.note} /> : <span className="text-muted-foreground">—</span> },
    ]
    return (
      <DataTable
        columns={cols}
        rows={rows}
        rowKey={(r) => r.id}
        caption="Incident categories · Lebanon, NH · YTD 2026"
      />
    )
  },
}

// ─── Existing basic stories ──────────────────────────────────────────────────

const INCIDENTS = [
  { case_number: '26-14755', reported_at: '2026-05-13', incident_type: 'Business Check',  officer: 'Benjamin Begin',       disposition: 'Log Information' },
  { case_number: '26-14753', reported_at: '2026-05-13', incident_type: 'Directed Patrol', officer: 'Sergeant James Pike',   disposition: 'Log Information' },
  { case_number: '26-14752', reported_at: '2026-05-13', incident_type: 'Business Check',  officer: 'Cpl. Jodi Dumayne',    disposition: 'Log Information' },
  { case_number: '26-14751', reported_at: '2026-05-13', incident_type: '911 Abandoned',   officer: 'Sergeant James Pike',   disposition: null },
  { case_number: '26-14750', reported_at: '2026-05-13', incident_type: 'Directed Patrol', officer: 'Benjamin Begin',       disposition: 'Log Information' },
]

const INCIDENT_COLS = [
  { id: 'case_number',   header: 'Case #',      sortable: true },
  { id: 'reported_at',   header: 'Date',        sortable: true },
  { id: 'incident_type', header: 'Type',        sortable: true },
  { id: 'officer',       header: 'Officer',     sortable: true },
  { id: 'disposition',   header: 'Disposition' },
]

export const Default: StoryObj = {
  render: () => <DataTable columns={INCIDENT_COLS} rows={INCIDENTS} rowKey={(r) => r.case_number} />,
}
export const Compact: StoryObj = {
  render: () => <DataTable columns={INCIDENT_COLS} rows={INCIDENTS} density="compact" rowKey={(r) => r.case_number} />,
}
export const Unborderd: StoryObj = {
  render: () => <DataTable columns={INCIDENT_COLS} rows={INCIDENTS} bordered={false} rowKey={(r) => r.case_number} />,
}
export const Clickable: StoryObj = {
  render: () => (
    <DataTable
      columns={INCIDENT_COLS}
      rows={INCIDENTS}
      rowKey={(r) => r.case_number}
      onRowClick={(row) => alert(`Selected: ${row.case_number}`)}
    />
  ),
}
export const Empty: StoryObj = {
  render: () => <DataTable columns={INCIDENT_COLS} rows={[]} empty="No incidents match the current filters." />,
}
