'use client'
import { HowWeCount } from '@/components/police-map/how-we-count'
import { TypeLabel } from '@/components/police-map/labels'
import { nameOf, sinceLabel, windowLabel } from '@/lib/police-map/format'
import { pinName } from '@/lib/police-map/map-style'
import { busiestDay, busiestHour, busiestPlaces } from '@/lib/police-map/summary'
import type { Address, StatsData } from '@/lib/types'

interface Props {
  addresses: Address[]
  stats: StatsData
  onChoose: (id: string) => void
  // What a count is made of, which a filter can narrow, such as "traffic stops and calls".
  noun?: string
}

const TOP_PLACES = 6
const TOP_TYPES = 6
const SECTION_HEADING =
  'mb-2 mt-6 font-mono text-xs font-medium uppercase tracking-widest text-muted-foreground'

// What the panel shows with nothing selected: the town as a whole.
export function TownSummary({ addresses, stats, onChoose, noun = 'log entries' }: Props) {
  const day = busiestDay(stats.by_weekday)
  const hour = busiestHour(stats.by_hour)

  return (
    <div>
      <div className="eyebrow">Lebanon, NH · {windowLabel(stats.since, stats.generated_at)}</div>
      <h2 className="text-display-3 mb-0.5 mt-1.5">The town at a glance</h2>
      <div className="mt-4 flex items-baseline gap-2.5">
        <b className="text-display-2 tabular-nums" style={{ fontFamily: 'var(--font-display)' }}>
          {stats.total.toLocaleString('en-US')}
        </b>
        <span className="text-muted-foreground">
          {noun} on the map since {sinceLabel(stats.since)}
        </span>
      </div>
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

      <h3 className={SECTION_HEADING}>Most activity</h3>
      <ol>
        {busiestPlaces(addresses, TOP_PLACES).map((place) => (
          <li key={place.id} className="border-b border-border">
            <button
              type="button"
              onClick={() => onChoose(place.id)}
              className="flex w-full justify-between gap-3 py-2 text-left text-sm hover:text-primary"
            >
              <span>{nameOf(pinName(place))}</span>
              <span className="font-mono text-sm text-muted-foreground">
                {place.count.toLocaleString('en-US')}
              </span>
            </button>
          </li>
        ))}
      </ol>
      <HowWeCount since={stats.since} />
    </div>
  )
}
