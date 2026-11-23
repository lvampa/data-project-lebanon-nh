import { HourStrip } from '@/components/police-views/hour-strip'
import { STATION_NOTE, whoStartedLine } from '@/lib/police-map/format'

// One pin's kept entries, for its card while filters are on.
export interface PinSummary {
  n: number
  hours: number[]
  // Typical minutes, or null with too few timed entries, and how many were timed.
  scene: number | null
  sceneTimed: number
  response: number | null
  responseTimed: number
  // With the place filter on: who started the entries, so a place opened from the Places tab
  // explains its bigger number. Null otherwise. The station is never on the Places tab.
  started: { fromPublic: number; byOfficers: number } | 'station' | null
}

// What the card needs from the views when filters are on.
export interface FilteredCard {
  // What a count is made of, such as "log entries" or "traffic stops and calls".
  noun: string
  summaryOf: (pinId: string) => PinSummary | null
  onClear: () => void
}

const SECTION_HEADING =
  'mb-2 mt-6 font-mono text-xs font-medium uppercase tracking-widest text-muted-foreground'

export function FilteredSection({
  name,
  summary,
  onClear,
}: {
  name: string
  summary: PinSummary | null
  onClear: () => void
}) {
  if (!summary || summary.n === 0) {
    return (
      <p className="mt-4 text-sm">
        No activity at {name} with these filters.{' '}
        <button
          type="button"
          onClick={onClear}
          className="font-medium text-primary hover:underline"
        >
          Clear filters
        </button>
      </p>
    )
  }
  return (
    <section>
      {summary.started === 'station' && (
        <p className="mt-1.5 text-sm text-muted-foreground">{STATION_NOTE}</p>
      )}
      {summary.started && summary.started !== 'station' && (
        <p className="mt-1.5 text-sm text-muted-foreground">
          {whoStartedLine(summary.started.fromPublic, summary.started.byOfficers)}
        </p>
      )}
      <h3 className={SECTION_HEADING}>Time of day, with your filters</h3>
      <HourStrip hours={summary.hours} />
      {summary.scene !== null && (
        <p className="mt-3 text-sm">
          <b className="font-semibold">Typical time on scene {summary.scene} min</b>, from{' '}
          {summary.sceneTimed.toLocaleString('en-US')} timed entries.
        </p>
      )}
      {summary.response !== null && (
        <p className="mt-1 text-sm">
          <b className="font-semibold">Typical time to arrive {summary.response} min</b>, from{' '}
          {summary.responseTimed.toLocaleString('en-US')} timed calls.{' '}
          <span className="text-muted-foreground">
            Walk-ins and calls with no arrival time are left out.
          </span>
        </p>
      )}
      <p className="mt-4 border-l-4 border-border pl-3 text-sm text-muted-foreground">
        The details below cover the whole year, not only your filters.
      </p>
    </section>
  )
}
