'use client'
import { useMemo } from 'react'
import { CATEGORIES } from '@/lib/police-map/categories'
import type { Activity } from '@/lib/police-views/activity'
import { tally, typical, wholeTown, TOWN } from '@/lib/police-views/counts'
import {
  allVisits,
  busyStretch,
  clock,
  partOfDay,
  directLabels,
  stayRows,
  typicalWeek,
  type StayRow,
  type WeekFlag,
} from '@/lib/police-views/findings'
import { weekNote, weekStart } from './weeks'

interface Props {
  activity: Activity
  kept: Uint8Array
  flags: WeekFlag[]
  // What the kept entries are, such as "log entries" or "traffic stops and calls".
  noun: string
}

const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
const MONTHS = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
]
// Monday first, the way a week reads.
const ROW_ORDER = [1, 2, 3, 4, 5, 6, 0]
const HEAT_STEPS = 4

const BOX = 'rounded-lg border border-border bg-card p-5'
const FINDING = 'mb-3.5 text-lg [&_b]:font-semibold [&_b]:text-highlight'

export function BusyTimesView({ activity, kept, flags, noun }: Props) {
  const town = useMemo(() => tally(activity, kept, wholeTown).get(TOWN) ?? null, [activity, kept])
  const grid = useMemo(() => heatGrid(activity, kept), [activity, kept])
  const stretch = busyStretch(grid)
  const empty = 'No activity matches these filters. Try a wider date range.'

  const stretchFinding = stretch ? (
    <>
      Police are busiest on{' '}
      <b>
        {stretch.weekdays ? 'weekday' : 'weekend'} {partOfDay(stretch.start + 1)},{' '}
        {clock(stretch.start)} to {clock(stretch.start + 3)}
      </b>
      . It is quietest from {clock(stretch.quietStart)} to {clock(stretch.quietStart + 3)}.
    </>
  ) : (
    empty
  )

  return (
    <section aria-labelledby="busy-heading" className="grid gap-4">
      <h2 id="busy-heading" className="text-display-3">
        When police are busiest
      </h2>

      <div className={BOX}>
        <p className={FINDING}>{stretchFinding}</p>
        <HeatMap grid={grid} noun={noun} />
      </div>

      <div className={BOX}>
        <WeekFinding activity={activity} weeks={town?.weeks ?? []} flags={flags} noun={noun} />
        <WeeklyChart activity={activity} kept={kept} flags={flags} />
      </div>

      <h2 className="mt-2 text-display-3">How long police stay</h2>
      <div className={BOX}>
        <StayChart rows={stayRows(activity, kept)} visits={allVisits(activity, kept)} />
      </div>
    </section>
  )
}

function heatGrid(activity: Activity, kept: Uint8Array): number[][] {
  const grid = Array.from({ length: 7 }, () => new Array(24).fill(0))
  for (let i = 0; i < activity.size; i++) {
    if (kept[i]) grid[activity.weekday[i]][activity.hour[i]]++
  }
  return grid
}

function HeatMap({ grid, noun }: { grid: number[][]; noun: string }) {
  const max = Math.max(1, ...grid.flat())
  const step = max / HEAT_STEPS
  const color = (value: number) =>
    value === 0
      ? 'var(--secondary)'
      : `var(--heat-${Math.min(HEAT_STEPS, Math.floor(value / step) + 1)})`
  return (
    // A phone has no room for 24 columns, so it keeps the finding above and drops the grid.
    <div className="hidden md:block">
      <div
        className="grid grid-cols-[40px_repeat(24,1fr)] gap-0.5"
        role="img"
        aria-label="Activity by day of the week and hour of the day"
      >
        <div />
        {Array.from({ length: 24 }, (_, hour) => (
          <div key={hour} className="text-center text-xs text-muted-foreground">
            {hour % 3 === 0 ? clock(hour) : ''}
          </div>
        ))}
        {ROW_ORDER.map((day) => (
          <Row key={day} day={day} values={grid[day]} color={color} noun={noun} />
        ))}
      </div>
      <div className="mt-2.5 flex flex-wrap gap-x-3.5 gap-y-1 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1.5">
          <i className="size-2.5 rounded-xs bg-secondary" /> None
        </span>
        {Array.from({ length: HEAT_STEPS }, (_, k) => (
          <span key={k} className="inline-flex items-center gap-1.5">
            <i className="size-2.5 rounded-xs" style={{ background: `var(--heat-${k + 1})` }} />
            {Math.max(1, Math.ceil(k * step)).toLocaleString('en-US')} to{' '}
            {Math.floor((k + 1) * step).toLocaleString('en-US')}
          </span>
        ))}
      </div>
    </div>
  )
}

function Row({
  day,
  values,
  color,
  noun,
}: {
  day: number
  values: number[]
  color: (value: number) => string
  noun: string
}) {
  return (
    <>
      <div className="text-xs leading-6 text-muted-foreground">{DAYS[day].slice(0, 3)}</div>
      {values.map((value, hour) => (
        <div
          key={hour}
          className="h-6 rounded-sm"
          style={{ background: color(value) }}
          data-tip-title={`${DAYS[day]}, ${clock(hour)} to ${clock(hour + 1)}`}
          data-tip={`${value.toLocaleString('en-US')} ${noun}`}
        />
      ))}
    </>
  )
}

function WeekFinding({
  activity,
  weeks,
  flags,
  noun,
}: {
  activity: Activity
  weeks: number[]
  flags: WeekFlag[]
  noun: string
}) {
  const week = typicalWeek(weeks, flags, activity.since)
  if (!week) return null
  return (
    <p className={FINDING}>
      About{' '}
      <b>
        {week.perWeek.toLocaleString('en-US')} {noun} a week
      </b>
      {week.steady ? ', steady all year.' : `, highest in ${MONTHS[week.topMonth]}.`}
    </p>
  )
}

const CHART_HEIGHT = 150

// Weeks stacked by kind, each kind labeled beside the last full week, so none is told apart
// by color alone.
function WeeklyChart({
  activity,
  kept,
  flags,
}: {
  activity: Activity
  kept: Uint8Array
  flags: WeekFlag[]
}) {
  const weeks = useMemo(() => {
    const byWeek = Array.from({ length: flags.length }, () => new Array(CATEGORIES.length).fill(0))
    for (let i = 0; i < activity.size; i++) {
      if (kept[i]) byWeek[activity.week[i]][activity.category[i]]++
    }
    return byWeek
  }, [activity, kept, flags.length])
  const totals = weeks.map((week) => week.reduce((a, b) => a + b, 0))
  const max = Math.max(1, ...totals)
  const kindTotals = CATEGORIES.map((_, k) => weeks.reduce((a, week) => a + week[k], 0))
  const labels = directLabels(weeks, flags, kindTotals, max, CHART_HEIGHT)

  return (
    <>
      <div className="grid grid-cols-[1fr_auto] gap-1.5">
        <div
          className="flex items-end gap-0.5 border-b border-border"
          style={{ height: CHART_HEIGHT }}
          role="img"
          aria-label="Activity by week, by kind"
        >
          {weeks.map((week, w) => (
            <div
              key={w}
              className="flex h-full min-w-0 flex-1 flex-col-reverse"
              data-tip-title={`Week of ${weekStart(activity.since, w)}: ${totals[w].toLocaleString('en-US')}`}
              data-tip={[
                ...CATEGORIES.flatMap((kind, k) =>
                  week[k] ? [`${kind.label}: ${week[k].toLocaleString('en-US')}`] : [],
                ),
                weekNote(flags[w]),
              ]
                .filter(Boolean)
                .join('\n')}
            >
              {CATEGORIES.map((kind, k) =>
                week[k] ? (
                  <i
                    key={kind.key}
                    className={`block border-t border-card last:rounded-t ${flags[w] ? 'week-incomplete' : ''}`}
                    style={{ height: `${(week[k] / max) * 100}%`, backgroundColor: kind.color }}
                  />
                ) : null,
              )}
            </div>
          ))}
        </div>
        <div className="relative min-w-32" style={{ height: CHART_HEIGHT }} aria-hidden>
          {labels.map((label) => (
            <span
              key={label.key}
              className="absolute left-0 flex -translate-y-1/2 items-center gap-1.5 whitespace-nowrap text-xs"
              style={{ top: label.y }}
            >
              <i className="h-1 w-2.5 rounded-sm" style={{ background: label.color }} />
              {label.label}
              <span className="font-mono text-muted-foreground">
                {label.total.toLocaleString('en-US')}
              </span>
            </span>
          ))}
        </div>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">Striped weeks are missing some logs.</p>
    </>
  )
}

function StayChart({ rows, visits }: { rows: StayRow[]; visits: number[] }) {
  const overall = typical(visits)
  if (rows.length === 0 || overall === null) {
    return <p className="text-muted-foreground">Not enough timed visits with these filters.</p>
  }
  const [longest, shortest] = [rows[0], rows[rows.length - 1]]
  const max = Math.max(...rows.map((row) => row.typical))
  return (
    <>
      <p className={FINDING}>
        A typical visit lasts <b>{overall} minutes</b>. The longest are &ldquo;{longest.label}
        &rdquo;, about {longest.typical} minutes. The quickest are &ldquo;{shortest.label}&rdquo;,
        about {shortest.typical}.
      </p>
      <div className="grid grid-cols-[minmax(120px,220px)_1fr_64px] items-center gap-x-3 gap-y-1.5 text-sm">
        {rows.map((row) => (
          <StayBar key={row.type} row={row} max={max} />
        ))}
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        Minutes from arrival to clearing, for a typical visit. Paid details and paperwork are left
        out.
      </p>
    </>
  )
}

function StayBar({ row, max }: { row: StayRow; max: number }) {
  return (
    <>
      <span data-tip-title={row.label} data-tip={`In the log: ${row.type}`}>
        {row.label}
      </span>
      <div
        className="h-5"
        role="img"
        aria-label={`${row.label}: about ${row.typical} minutes`}
        data-tip-title={row.label}
        data-tip={`Typical visit ${row.typical} min.\nHalf of visits take ${row.low} to ${row.high} min.\nFrom ${row.n.toLocaleString('en-US')} timed entries.`}
      >
        <i
          className="block h-full rounded-r"
          style={{ width: `${(row.typical / max) * 100}%`, background: 'var(--chart-ink)' }}
        />
      </div>
      <span className="text-right font-mono text-sm text-muted-foreground">{row.typical} min</span>
    </>
  )
}
