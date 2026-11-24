'use client'
import dynamic from 'next/dynamic'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Tabs } from '@project/ui/components/ui/tabs'
import type { FilteredCard, PinSummary } from '@/components/police-map/filtered-section'
import type { Activity } from '@/lib/police-views/activity'
import {
  cardGroupOf,
  filteredAddresses,
  tally,
  topOf,
  typical,
  wholeTown,
  TOWN,
} from '@/lib/police-views/counts'
import {
  DEFAULT_FILTERS,
  VIEWS,
  isDefault,
  nounFor,
  rangeDays,
  rangeLabel,
  readQuery,
  withRoadsKind,
  writeQuery,
  type Filters,
  type View,
} from '@/lib/police-views/filters'
import { weekFlags, weeksInRange } from '@/lib/police-views/findings'
import { STATION_ID, lastDayOf, selectEntries } from '@/lib/police-views/select'
import type { RoadsMode } from '@/lib/police-views/roads'
import type { Address, StatsData } from '@/lib/types'
import { BusyTimesView } from './busy-times-view'
import { ChartTooltip } from './chart-tooltip'
import { FilterBar } from './filter-bar'
import { OfficersView } from './officers-view'
import { PlacesView } from './places-view'
import { RoadsView } from './roads-view'
import { useActivity } from './use-activity'

// MapLibre needs the browser, so the map is not prerendered.
const PoliceMap = dynamic(
  () => import('@/components/police-map/police-map').then((m) => m.PoliceMap),
  {
    ssr: false,
    loading: () => (
      <div className="police-map-stage place-items-center rounded-lg border text-sm text-muted-foreground">
        Loading the map…
      </div>
    ),
  },
)

interface State {
  view: View
  filters: Filters
  mode: RoadsMode
}

interface Props {
  addresses: Address[]
  stats: StatsData
}

export function PoliceViews({ addresses, stats }: Props) {
  const [{ view, filters: asRead, mode }, setState] = useState<State>({
    view: 'map',
    filters: DEFAULT_FILTERS,
    mode: 'roads',
  })
  // Roads count every entry or only traffic, so a link with another kind opens on all.
  const filters = withRoadsKind(view, asRead)

  // The query is read after the first render, so the static page and the browser agree.
  useEffect(() => {
    const read = () => setState(readQuery(window.location.search))
    read()
  }, [])

  const go = useCallback((next: State) => {
    setState(next)
    const { pathname, hash } = window.location
    window.history.replaceState(
      null,
      '',
      `${pathname}${writeQuery(next.view, next.filters, next.mode)}${hash}`,
    )
  }, [])
  const setFilters = (next: Filters) => go({ view, filters: next, mode })

  const wanted = view !== 'map' || !isDefault(filters)
  const state = useActivity(addresses, wanted)
  const activity = state.status === 'ready' ? state.activity : null

  const derived = useDerived(activity, addresses, stats, filters)

  // A place chosen on another tab opens on the map, which reads the selection from the hash.
  // Places counts calls about a place, so the map opens on that kind, and the pin is there.
  const showOnMap = (id: string, onMap: Filters) => {
    const { pathname } = window.location
    window.history.replaceState(null, '', `${pathname}${writeQuery('map', onMap, mode)}#${id}`)
    setState({ view: 'map', filters: onMap, mode })
  }
  const showPlace = (id: string) => showOnMap(id, { ...filters, kind: 'place' })
  // A road counts every kind of entry on it, so the map keeps the filters as they are.
  const showRoad = (id: string) => showOnMap(id, filters)
  const showOfficer = (officer: string) =>
    go({ view: 'map', filters: { ...filters, officer }, mode })

  const onMap = view === 'map'

  // The header keeps the layout's width on every tab, so switching tabs never moves it.
  // Only the map runs the full width of the window, keeping the page's side padding; the
  // body clips the scrollbar overflow of w-screen.
  return (
    <div className={onMap ? 'police-map-page' : undefined}>
      <div className="shrink-0">
        <div className="eyebrow">Public safety · Updated {updatedOf(stats)}</div>
        <h1 className="mb-3 mt-1.5 text-display-2">Police activity in Lebanon</h1>
        <Tabs
          // Four tabs are wider than a small phone, so the row scrolls sideways. The 1px of
          // padding holds the active underline, which sits 1px low, so it never scrolls down.
          className="mb-3.5 w-full overflow-x-auto pb-px"
          items={VIEWS.map((v) => ({ id: v.id, label: v.label }))}
          value={view}
          onChange={(id) => go({ view: id as View, filters, mode })}
        />
        <FilterBar
          filters={filters}
          onChange={setFilters}
          count={derived ? derived.countLine(view) : null}
          lens={view === 'places' ? 'Calls from the public only' : null}
          roadsKind={view === 'roads'}
          showOfficer={view !== 'officers'}
        />
      </div>

      {onMap ? (
        <div className="relative left-1/2 min-h-0 w-screen flex-1 -translate-x-1/2 px-5 md:px-8">
          <PoliceMap
            addresses={addresses}
            shown={derived && !isDefault(filters) ? derived.mapAddresses : undefined}
            stats={derived && !isDefault(filters) ? derived.mapStats : stats}
            filtered={
              derived && !isDefault(filters)
                ? derived.card(() => setFilters(DEFAULT_FILTERS))
                : null
            }
          />
        </div>
      ) : (
        <div>
          {state.status === 'error' ? (
            <LoadError onRetry={state.retry} />
          ) : !activity || !derived ? (
            <p className="py-10 text-muted-foreground">Loading the activity…</p>
          ) : view === 'places' ? (
            <PlacesView
              addresses={addresses}
              activity={activity}
              kept={derived.publicKept}
              filters={filters}
              range={derived.weeks}
              onShow={showPlace}
            />
          ) : view === 'roads' ? (
            <RoadsView
              addresses={derived.mapAddresses}
              activity={activity}
              kept={derived.kept}
              range={derived.weeks}
              mode={mode}
              onMode={(next) => go({ view, filters, mode: next })}
              onShow={showRoad}
            />
          ) : view === 'busy' ? (
            <BusyTimesView
              activity={activity}
              kept={derived.kept}
              range={derived.weeks}
              noun={nounFor(filters.kind)}
              coverage={coverageOf(activity, stats)}
            />
          ) : (
            <OfficersView
              activity={activity}
              kept={derived.everyOfficerKept}
              noun={nounFor(filters.kind)}
              rangeLabel={derived.rangeText}
              coverage={coverageOf(activity, stats)}
              onShow={showOfficer}
            />
          )}
        </div>
      )}
      {onMap && state.status === 'error' && <LoadError onRetry={state.retry} />}
      <ChartTooltip />
    </div>
  )
}

// Everything the views count, worked out once per change of data or filters.
function useDerived(
  activity: Activity | null,
  addresses: Address[],
  stats: StatsData,
  filters: Filters,
) {
  return useMemo(() => {
    if (!activity) return null
    const lastDay = lastDayOf(activity)
    const firstDay = lastDay - rangeDays(filters.range) + 1
    const kept = selectEntries(activity, addresses, filters, 'all')
    const publicKept = selectEntries(activity, addresses, filters, 'public')
    const everyOfficerKept = selectEntries(
      activity,
      addresses,
      { ...filters, officer: null },
      'all',
    )
    // The same kind with no other filter, for "1,204 of 19,316".
    const kindOnly = { ...DEFAULT_FILTERS, kind: filters.kind }
    const narrowedButOfficer = filters.time !== kindOnly.time || filters.range !== kindOnly.range
    const narrowed = narrowedButOfficer || filters.officer !== null
    const sum = (mask: Uint8Array) => mask.reduce((a, v) => a + v, 0)
    const shown = { all: sum(kept), public: sum(publicKept), everyOfficer: sum(everyOfficerKept) }
    const totals = narrowed
      ? {
          all: sum(selectEntries(activity, addresses, kindOnly, 'all')),
          public: sum(selectEntries(activity, addresses, kindOnly, 'public')),
        }
      : { all: shown.all, public: shown.public }

    const pins = tally(activity, kept, (i) => activity.pin[i])
    // A street's filtered numbers count the places listed on it, as its headline does.
    const cards = tally(activity, kept, cardGroupOf(activity, addresses))
    const publicPins = tally(activity, publicKept, (i) => activity.pin[i])
    const publicCards = tally(activity, publicKept, cardGroupOf(activity, addresses))
    const town = tally(activity, kept, wholeTown).get(TOWN)
    const pinIndex = new Map(addresses.map((address, index) => [address.id, index]))

    return {
      kept,
      publicKept,
      everyOfficerKept,
      weeks: weeksInRange(weekFlags(activity), firstDay),
      rangeText: rangeLabel(activity.since, lastDay, filters.range),
      mapAddresses: filteredAddresses(addresses, activity, kept),
      mapStats: {
        ...stats,
        // The summary and the legend name the range, not the whole year.
        since: dayToIso(activity.since, Math.max(0, firstDay)),
        total: shown.all,
        by_weekday: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day, d) => ({
          day,
          count: town?.weekdays[d] ?? 0,
        })),
        by_hour: (town?.hours ?? []).map((count, hour) => ({ hour, count })),
        by_type: topOf(town?.types ?? new Map(), 6).map(([type, count]) => ({
          incident_type: activity.types[type] ?? 'Unknown',
          count,
        })),
      } satisfies StatsData,
      countLine(view: View): string {
        // The Officers tab lists every officer and hides the officer filter, so its line
        // leaves that filter out too.
        if (view === 'officers') {
          const n = shown.everyOfficer.toLocaleString('en-US')
          const noun = nounFor(filters.kind)
          const total = totals.all.toLocaleString('en-US')
          return narrowedButOfficer ? `${n} of ${total} ${noun}` : `${n} ${noun}`
        }
        const lens = view === 'places' ? 'public' : 'all'
        const noun = view === 'places' ? 'calls from the public' : nounFor(filters.kind)
        const n = shown[lens].toLocaleString('en-US')
        return narrowed ? `${n} of ${totals[lens].toLocaleString('en-US')} ${noun}` : `${n} ${noun}`
      },
      card(onClear: () => void): FilteredCard {
        return {
          noun: nounFor(filters.kind),
          onClear,
          summaryOf(pinId: string): PinSummary | null {
            const index = pinIndex.get(pinId) ?? -1
            // A place listed on its street opens its own card, so it takes its own tally.
            const listedOnStreet = addresses[index]?.hidden
            const t = listedOnStreet ? pins.get(index) : cards.get(index)
            if (!t) return null
            const fromPublic = (listedOnStreet ? publicPins : publicCards).get(index)?.n ?? 0
            return {
              n: t.n,
              hours: t.hours,
              scene: typical(t.scenes),
              sceneTimed: t.scenes.length,
              response: typical(t.responses),
              responseTimed: t.responses.length,
              started:
                filters.kind !== 'place'
                  ? null
                  : pinId === STATION_ID
                    ? 'station'
                    : { fromPublic, byOfficers: t.initiated },
            }
          },
        }
      },
    }
  }, [activity, addresses, stats, filters])
}

// Entries whose address has no point yet are not in activity.json, so the views say so.
function coverageOf(activity: Activity, stats: StatsData): string {
  const mapped = activity.size.toLocaleString('en-US')
  return `Counts the ${mapped} log entries with a mapped location, of ${stats.total.toLocaleString('en-US')} in the log.`
}

// "2026-08-22" for day 233 after "2026-01-01".
function dayToIso(since: string, day: number): string {
  const start = new Date(`${since}T00:00:00Z`).getTime()
  return new Date(start + day * 86_400_000).toISOString().slice(0, 10)
}

function updatedOf(stats: StatsData): string {
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    month: 'short',
    day: 'numeric',
  }).format(new Date(stats.generated_at))
}

function LoadError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="mt-4 rounded-lg border border-border bg-muted p-3 text-sm">
      <p>The activity did not load, so the filters and these views are not available.</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-2 font-medium text-primary underline underline-offset-4"
      >
        Try again
      </button>
    </div>
  )
}
