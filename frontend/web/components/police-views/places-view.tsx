'use client'
import { useMemo, useState } from 'react'
import { Tabs } from '@project/ui/components/ui/tabs'
import { TypeLabel } from '@/components/police-map/labels'
import { nameOf, streetOf } from '@/lib/police-map/format'
import { pinName } from '@/lib/police-map/map-style'
import type { Activity } from '@/lib/police-views/activity'
import { tally, topOf, type Tally } from '@/lib/police-views/counts'
import { type Filters } from '@/lib/police-views/filters'
import type { WeekRange } from '@/lib/police-views/findings'
import { selectEntries } from '@/lib/police-views/select'
import type { Address } from '@/lib/types'
import { HourStrip } from './hour-strip'
import { WeekBars } from './week-bars'

interface Props {
  addresses: Address[]
  activity: Activity
  // The public lens, from the page, so the count line and the cards agree.
  kept: Uint8Array
  filters: Filters
  // The weeks the date range covers.
  range: WeekRange
  onShow: (id: string) => void
}

const SHOWN = 60
// "Most at night" only ranks places with enough calls for a share to mean something.
const MIN_FOR_SHARE = 20

type Sort = 'count' | 'night'

export function PlacesView({ addresses, activity, kept, filters, range, onShow }: Props) {
  const [sort, setSort] = useState<Sort>('count')
  const places = useMemo(() => tally(activity, kept, (i) => activity.pin[i]), [activity, kept])
  const falseAlarms = useMemo(
    () => falseAlarmsByPin(activity, addresses, filters),
    [activity, addresses, filters],
  )

  const ranked = [...places]
    .filter(([, t]) => sort === 'count' || t.n >= MIN_FOR_SHARE)
    .sort(([a, ta], [b, tb]) =>
      sort === 'count'
        ? tb.n - ta.n || a - b
        : tb.night / tb.n - ta.night / ta.n || tb.n - ta.n || a - b,
    )
    .slice(0, SHOWN)
  // One scale for every card, so the bars compare across places.
  const weekMax = Math.max(1, ...ranked.flatMap(([, t]) => t.weeks.slice(range.first)))

  return (
    <section aria-labelledby="places-heading">
      <div className="mb-3.5 flex flex-wrap items-end justify-between gap-2.5">
        <div>
          <h2 id="places-heading" className="text-display-3">
            Places police were called to most
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Calls from the public about something at the place. Leaves out traffic stops, officer
            patrols and checks, false alarms, and the police station.
          </p>
        </div>
        <Tabs
          variant="pill"
          items={[
            { id: 'count', label: 'Most calls' },
            { id: 'night', label: 'Most at night' },
          ]}
          value={sort}
          onChange={(id) => setSort(id as Sort)}
        />
      </div>

      {ranked.length === 0 ? (
        <p className="text-muted-foreground">
          No calls match these filters. Try a wider date range.
        </p>
      ) : (
        <ol className="grid grid-cols-1 gap-3 sm:grid-cols-[repeat(auto-fill,minmax(270px,1fr))]">
          {ranked.map(([pin, t], index) => (
            <li key={pin} className="grid">
              <PlaceTile
                rank={index + 1}
                address={addresses[pin]}
                tally={t}
                falseAlarms={falseAlarms.get(pin) ?? 0}
                showNight={filters.time === 'all'}
                weekMax={weekMax}
                range={range}
                since={activity.since}
                types={activity.types}
                onShow={onShow}
              />
            </li>
          ))}
        </ol>
      )}
      <p className="mt-3.5 text-sm text-muted-foreground">
        Each card uses the same scale, so you can compare them. Night is 7pm to 7am, and Most at
        night only ranks places with {MIN_FOR_SHARE} calls or more. Striped weeks are missing some
        logs. The station is left out because the log files reports taken there under the station,
        not where they happened.
      </p>
    </section>
  )
}

function PlaceTile({
  rank,
  address,
  tally: t,
  falseAlarms,
  showNight,
  weekMax,
  range,
  since,
  types,
  onShow,
}: {
  rank: number
  address: Address
  tally: Tally
  falseAlarms: number
  showNight: boolean
  weekMax: number
  range: WeekRange
  since: string
  types: (string | null)[]
  onShow: (id: string) => void
}) {
  const name = pinName(address)
  const [top] = topOf(t.types, 1)
  return (
    <article className="flex flex-col rounded-lg border border-border bg-card p-4">
      <div className="flex items-baseline justify-between">
        <span className="font-mono text-xs text-muted-foreground">#{rank}</span>
        <b
          className="text-display-3 tabular-nums leading-none"
          style={{ fontFamily: 'var(--font-display)' }}
        >
          {t.n.toLocaleString('en-US')}
        </b>
      </div>
      <h3 className="mt-2 font-semibold leading-tight">{nameOf(name)}</h3>
      <div className="min-h-5 text-sm text-muted-foreground">{streetOf(name)}</div>
      <WeekBars
        weeks={t.weeks.slice(range.first)}
        first={range.first}
        max={weekMax}
        flags={range.flags}
        since={since}
        noun="calls"
      />
      <HourStrip hours={t.hours} compact />
      <div className="mt-2.5 grid gap-0.5 text-sm text-muted-foreground">
        {showNight && (
          <span>
            <b className="font-medium text-foreground">{Math.round((100 * t.night) / t.n)}%</b> at
            night
          </span>
        )}
        {top && (
          <span>
            Most common:{' '}
            <b className="font-medium text-foreground">
              <TypeLabel type={types[top[0]]} />
            </b>
          </span>
        )}
        {falseAlarms > 0 && (
          <span>
            {falseAlarms.toLocaleString('en-US')} false {falseAlarms === 1 ? 'alarm' : 'alarms'},
            not counted above
          </span>
        )}
      </div>
      <button
        type="button"
        onClick={() => onShow(address.id)}
        className="mt-2.5 self-start text-sm font-medium text-primary hover:underline"
      >
        Show on the map →
      </button>
    </article>
  )
}

// A place's false alarms, under the same dates, hours and officer as its calls.
function falseAlarmsByPin(
  activity: Activity,
  addresses: Address[],
  filters: Filters,
): Map<number, number> {
  const alarms = selectEntries(activity, addresses, { ...filters, kind: 'alarms' }, 'all')
  const falseAlarm = activity.dispositions.indexOf('False Alarm')
  const counts = new Map<number, number>()
  for (let i = 0; i < activity.size; i++) {
    if (!alarms[i] || activity.disposition[i] !== falseAlarm) continue
    const pin = activity.pin[i]
    if (addresses[pin].kind !== 'place') continue
    counts.set(pin, (counts.get(pin) ?? 0) + 1)
  }
  return counts
}
