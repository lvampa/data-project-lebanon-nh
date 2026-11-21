'use client'
import dynamic from 'next/dynamic'
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Tabs } from '@project/ui/components/ui/tabs'
import type { FilteredCard, PinSummary } from '@/components/police-map/filtered-section'
import type { Activity } from '@/lib/police-views/activity'
import {
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
  rangeLabel,
  readQuery,
  writeQuery,
  type Filters,
  type View,
} from '@/lib/police-views/filters'
import { weekFlags } from '@/lib/police-views/findings'
import { lastDayOf, selectEntries } from '@/lib/police-views/select'
import type { Address, StatsData } from '@/lib/types'
import { BusyTimesView } from './busy-times-view'
import { ChartTooltip } from './chart-tooltip'
import { FilterBar } from './filter-bar'
import { OfficersView } from './officers-view'
import { PlacesView } from './places-view'
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

interface Props {
  addresses: Address[]
  stats: StatsData
}

// Space kept under the map, so its bottom edge shows.
const BELOW_MAP = 16

export function PoliceViews({ addresses, stats }: Props) {
  const [{ view, filters }, setState] = useState<{ view: View; filters: Filters }>({
    view: 'map',
    filters: DEFAULT_FILTERS,
  })
  const [attempt, setAttempt] = useState(0)

  // The query is read after the first render, so the static page and the browser agree.
  useEffect(() => {
    const read = () => setState(readQuery(window.location.search))
    read()
  }, [])

  const go = useCallback((next: { view: View; filters: Filters }) => {
    setState(next)
    const { pathname, hash } = window.location
    window.history.replaceState(
      null,
      '',
      `${pathname}${writeQuery(next.view, next.filters)}${hash}`,
    )
  }, [])
  const setFilters = (next: Filters) => go({ view, filters: next })

  const wanted = view !== 'map' || !isDefault(filters)
  const state = useActivity(addresses, wanted, attempt)
  const activity = state.status === 'ready' ? state.activity : null

  const derived = useDerived(activity, addresses, stats, filters)

  // A place chosen on another tab opens on the map, which reads the selection from the hash.
  const showPlace = (id: string) => {
    const { pathname } = window.location
    window.history.replaceState(null, '', `${pathname}${writeQuery('map', filters)}#${id}`)
    setState({ view: 'map', filters })
  }
  const showOfficer = (officer: string) => go({ view: 'map', filters: { ...filters, officer } })

  const onMap = view === 'map'
  const width = onMap ? '' : 'mx-auto max-w-7xl'

  return (
    <div>
      <div className={width}>
        <div className="eyebrow">Public safety · Updated {updatedOf(stats)}</div>
        <h1 className="mb-3 mt-1.5 text-display-2">Police activity in Lebanon</h1>
        <Tabs
          className="mb-3.5 w-full overflow-x-auto"
          items={VIEWS.map((v) => ({ id: v.id, label: v.label }))}
          value={view}
          onChange={(id) => go({ view: id as View, filters })}
        />
        <FilterBar
          filters={filters}
          onChange={setFilters}
          count={derived ? derived.countLine(view) : null}
          lens={view === 'places' ? 'Calls from the public only' : null}
          showOfficer={view !== 'officers'}
        />
      </div>

      {onMap ? (
        <FittedMap>
          <PoliceMap
            addresses={derived && !isDefault(filters) ? derived.mapAddresses : addresses}
            stats={derived && !isDefault(filters) ? derived.mapStats : stats}
            filtered={
              derived && !isDefault(filters)
                ? derived.card(() => setFilters(DEFAULT_FILTERS))
                : null
            }
          />
        </FittedMap>
      ) : (
        <div className={width}>
          {state.status === 'error' ? (
            <LoadError onRetry={() => setAttempt((n) => n + 1)} />
          ) : !activity || !derived ? (
            <p className="py-10 text-muted-foreground">Loading the activity…</p>
          ) : view === 'places' ? (
            <PlacesView
              addresses={addresses}
              activity={activity}
              kept={derived.publicKept}
              filters={filters}
              flags={derived.flags}
              onShow={showPlace}
            />
          ) : view === 'busy' ? (
            <BusyTimesView
              activity={activity}
              kept={derived.kept}
              flags={derived.flags}
              noun={nounFor(filters.kind)}
            />
          ) : (
            <OfficersView
              activity={activity}
              kept={derived.everyOfficerKept}
              noun={nounFor(filters.kind)}
              rangeLabel={derived.range}
              onShow={showOfficer}
            />
          )}
        </div>
      )}
      {onMap && state.status === 'error' && <LoadError onRetry={() => setAttempt((n) => n + 1)} />}
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
    const narrowed =
      filters.time !== kindOnly.time || filters.range !== kindOnly.range || filters.officer !== null
    const sum = (mask: Uint8Array) => mask.reduce((a, v) => a + v, 0)
    const shown = { all: sum(kept), public: sum(publicKept) }
    const totals = narrowed
      ? {
          all: sum(selectEntries(activity, addresses, kindOnly, 'all')),
          public: sum(selectEntries(activity, addresses, kindOnly, 'public')),
        }
      : shown

    const pins = tally(activity, kept, (i) => activity.pin[i])
    const town = tally(activity, kept, wholeTown).get(TOWN)
    const pinIndex = new Map(addresses.map((address, index) => [address.id, index]))

    return {
      kept,
      publicKept,
      everyOfficerKept,
      flags: weekFlags(activity),
      range: rangeLabel(activity.since, lastDay, filters.range),
      mapAddresses: filteredAddresses(addresses, activity, kept),
      mapStats: {
        ...stats,
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
            const t = pins.get(pinIndex.get(pinId) ?? -1)
            if (!t) return null
            return {
              n: t.n,
              hours: t.hours,
              scene: typical(t.scenes),
              sceneTimed: t.scenes.length,
              response: typical(t.responses),
              responseTimed: t.responses.length,
            }
          },
        }
      },
    }
  }, [activity, addresses, stats, filters])
}

function updatedOf(stats: StatsData): string {
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    month: 'short',
    day: 'numeric',
  }).format(new Date(stats.generated_at))
}

// The map fills the window under the tabs and filters, so the whole map shows at the top
// of the page. Measured, because the filter bar's height changes with what it holds.
function FittedMap({ children }: { children: React.ReactNode }) {
  const box = useRef<HTMLDivElement>(null)
  useLayoutEffect(() => {
    const fit = () => {
      const node = box.current
      if (!node) return
      const top = node.getBoundingClientRect().top + window.scrollY
      node.style.setProperty(
        '--map-height',
        `${Math.round(window.innerHeight - top - BELOW_MAP)}px`,
      )
    }
    fit()
    window.addEventListener('resize', fit)
    return () => window.removeEventListener('resize', fit)
  }, [])
  return <div ref={box}>{children}</div>
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
