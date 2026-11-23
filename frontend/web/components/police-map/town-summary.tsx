'use client'
import { HowWeCount } from '@/components/police-map/how-we-count'
import { TypeLabel } from '@/components/police-map/labels'
import { nameOf, sinceLabel, windowLabel } from '@/lib/police-map/format'
import { pinName } from '@/lib/police-map/map-style'
import {
  busiestDay,
  busiestHour,
  busiestPlaces,
  busiestStreets,
  mappedTotal,
} from '@/lib/police-map/summary'
import type { Address, StatsData } from '@/lib/types'

interface Props {
  addresses: Address[]
  stats: StatsData
  onChoose: (id: string) => void
  // What a count is made of, which a filter can narrow, such as "traffic stops and calls".
  noun?: string
  // With filters on, `stats` already counts only the entries on the map.
  filtered?: boolean
}

const TOP_LISTED = 5
const TOP_TYPES = 6
const SECTION_HEADING =
  'mb-2 mt-6 font-mono text-xs font-medium uppercase tracking-widest text-muted-foreground'

// What the panel shows with nothing selected: the town as a whole.
export function TownSummary({
  addresses,
  stats,
  onChoose,
  noun = 'log entries',
  filtered = false,
}: Props) {
  const day = busiestDay(stats.by_weekday)
  const hour = busiestHour(stats.by_hour)
  // Every number on this page counts entries with a spot on the map, so the total does too.
  // The export counts it; an older stats.json without it is summed from the pins.
  const onMap = filtered ? stats.total : (stats.mapped_total ?? mappedTotal(addresses))
  const unmapped = filtered ? 0 : stats.total - onMap

  return (
    <div>
      <div className="eyebrow">Lebanon, NH · {windowLabel(stats.since, stats.generated_at)}</div>
      <h2 className="text-display-3 mb-0.5 mt-1.5">The town at a glance</h2>
      <div className="mt-4 flex items-baseline gap-2.5">
        <b className="text-display-2 tabular-nums" style={{ fontFamily: 'var(--font-display)' }}>
          {onMap.toLocaleString('en-US')}
        </b>
        <span className="text-muted-foreground">
          {noun} on the map since {sinceLabel(stats.since)}
        </span>
      </div>
      {unmapped > 0 && (
        <div className="mt-1 text-sm text-muted-foreground">
          Another {unmapped.toLocaleString('en-US')} have no mapped location yet.
        </div>
      )}
      {day && hour && (
        <p className="mb-1 mt-3 text-base">
          Busiest day: <b className="font-semibold text-highlight">{day}</b>. Busiest hour:{' '}
          <b className="font-semibold text-highlight">{hour}</b>.
        </p>
      )}
      <p className="text-muted-foreground">
        Pick a circle or search for an address to see its activity.
      </p>

      {stats.by_type.length > 0 && (
        <>
          <h3 className={SECTION_HEADING}>What police spent time on</h3>
          <ol>
            {stats.by_type.slice(0, TOP_TYPES).map((row) => (
              <li
                key={row.incident_type}
                className="flex justify-between gap-3 border-b border-border py-2 text-sm"
              >
                <span>
                  <TypeLabel type={row.incident_type} />
                </span>
                <span className="font-mono text-sm text-muted-foreground">
                  {row.count.toLocaleString('en-US')}
                </span>
              </li>
            ))}
          </ol>
        </>
      )}

      <h3 className={SECTION_HEADING}>Busiest places</h3>
      <BusiestList
        rows={busiestPlaces(addresses, TOP_LISTED).map((a) => ({ address: a, total: a.count }))}
        onChoose={onChoose}
      />
      <h3 className={SECTION_HEADING}>Busiest streets</h3>
      <BusiestList rows={busiestStreets(addresses, TOP_LISTED)} onChoose={onChoose} />
      <HowWeCount since={stats.since} />
    </div>
  )
}

function BusiestList({
  rows,
  onChoose,
}: {
  rows: { address: Address; total: number }[]
  onChoose: (id: string) => void
}) {
  return (
    <ol>
      {rows.map(({ address, total }) => (
        <li key={address.id} className="border-b border-border">
          <button
            type="button"
            onClick={() => onChoose(address.id)}
            className="flex w-full justify-between gap-3 py-2 text-left text-sm hover:text-primary"
          >
            <span>{nameOf(pinName(address))}</span>
            <span className="font-mono text-sm text-muted-foreground">
              {total.toLocaleString('en-US')}
            </span>
          </button>
        </li>
      ))}
    </ol>
  )
}
