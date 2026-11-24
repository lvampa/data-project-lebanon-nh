'use client'
import { useMemo } from 'react'
import { Tabs } from '@project/ui/components/ui/tabs'
import type { Activity } from '@/lib/police-views/activity'
import { tally } from '@/lib/police-views/counts'
import type { WeekRange } from '@/lib/police-views/findings'
import {
  ROADS_MODES,
  buildRoads,
  type Crossing,
  type Road,
  type RoadsMode,
} from '@/lib/police-views/roads'
import type { Address } from '@/lib/types'
import { WeekBars } from './week-bars'

interface Props {
  addresses: Address[]
  activity: Activity
  kept: Uint8Array
  // The weeks the date range covers.
  range: WeekRange
  mode: RoadsMode
  onMode: (mode: RoadsMode) => void
  onShow: (id: string) => void
}

const SHOWN = 60
const TOP_CROSSINGS = 3

export function RoadsView({ addresses, activity, kept, range, mode, onMode, onShow }: Props) {
  const { roads, crossings } = useMemo(
    () =>
      buildRoads(
        addresses,
        tally(activity, kept, (i) => activity.pin[i]),
      ),
    [addresses, activity, kept],
  )
  const shown = (mode === 'roads' ? roads : crossings).slice(0, SHOWN)
  // One scale for every card, so the bars compare across cards.
  const weekMax = Math.max(1, ...shown.flatMap((item) => item.weeks.slice(range.first)))

  return (
    <section aria-labelledby="roads-heading">
      <div className="mb-3.5 flex flex-wrap items-end justify-between gap-2.5">
        <div>
          <h2 id="roads-heading" className="text-display-3">
            {mode === 'roads' ? 'Roads with the most activity' : 'Crossings with the most activity'}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {mode === 'roads'
              ? 'A road and its crossings: the entries on the road itself, plus the entries where it meets another road.'
              : 'Entries at the point where two roads meet.'}{' '}
            Places listed on a road are on the Places tab, not here.
          </p>
        </div>
        <Tabs
          variant="pill"
          items={ROADS_MODES.map((m) => ({ id: m.id, label: m.label }))}
          value={mode}
          onChange={(id) => onMode(id as RoadsMode)}
        />
      </div>

      {shown.length === 0 ? (
        <p className="text-muted-foreground">
          No entries match these filters. Try a wider date range.
        </p>
      ) : (
        <ol className="grid grid-cols-1 gap-3 sm:grid-cols-[repeat(auto-fill,minmax(270px,1fr))]">
          {shown.map((item, index) => (
            <li key={'showId' in item ? item.name : item.id} className="grid">
              {'showId' in item ? (
                <RoadTile
                  rank={index + 1}
                  road={item}
                  weekMax={weekMax}
                  range={range}
                  since={activity.since}
                  onShow={onShow}
                />
              ) : (
                <CrossingTile
                  rank={index + 1}
                  crossing={item}
                  weekMax={weekMax}
                  range={range}
                  since={activity.since}
                  onShow={onShow}
                />
              )}
            </li>
          ))}
        </ol>
      )}
      <p className="mt-3.5 text-sm text-muted-foreground">
        A crossing counts toward both of its roads, so roads don&apos;t add up to the town total.
        Each card uses the same scale, so you can compare them. Striped weeks are missing some logs.
      </p>
    </section>
  )
}

function Header({ rank, total }: { rank: number; total: number }) {
  return (
    <div className="flex items-baseline justify-between">
      <span className="font-mono text-xs text-muted-foreground">#{rank}</span>
      <b
        className="text-display-3 tabular-nums leading-none"
        style={{ fontFamily: 'var(--font-display)' }}
      >
        {total.toLocaleString('en-US')}
      </b>
    </div>
  )
}

function ShowOnMap({ id, onShow }: { id: string; onShow: (id: string) => void }) {
  return (
    <button
      type="button"
      onClick={() => onShow(id)}
      className="mt-2.5 self-start text-sm font-medium text-primary hover:underline"
    >
      Show on the map →
    </button>
  )
}

function RoadTile({
  rank,
  road,
  weekMax,
  range,
  since,
  onShow,
}: {
  rank: number
  road: Road
  weekMax: number
  range: WeekRange
  since: string
  onShow: (id: string) => void
}) {
  const top = road.crossings.slice(0, TOP_CROSSINGS)
  return (
    <article className="flex flex-col rounded-lg border border-border bg-card p-4">
      <Header rank={rank} total={road.total} />
      <h3 className="mt-2 font-semibold leading-tight">{road.name}</h3>
      <WeekBars
        weeks={road.weeks.slice(range.first)}
        first={range.first}
        max={weekMax}
        flags={range.flags}
        since={since}
        noun="entries"
      />
      <div className="mt-2.5 grid gap-0.5 text-sm text-muted-foreground">
        <span>
          <b className="font-medium text-foreground">{road.own.toLocaleString('en-US')}</b> on the
          road ·{' '}
          <b className="font-medium text-foreground">{road.atCrossings.toLocaleString('en-US')}</b>{' '}
          at {road.crossings.length.toLocaleString('en-US')}{' '}
          {road.crossings.length === 1 ? 'crossing' : 'crossings'}
        </span>
        {top.length > 0 && (
          <span>{top.map((c) => `${c.other} ${c.n.toLocaleString('en-US')}`).join(' · ')}</span>
        )}
      </div>
      <ShowOnMap id={road.showId} onShow={onShow} />
    </article>
  )
}

function CrossingTile({
  rank,
  crossing,
  weekMax,
  range,
  since,
  onShow,
}: {
  rank: number
  crossing: Crossing
  weekMax: number
  range: WeekRange
  since: string
  onShow: (id: string) => void
}) {
  const [a, b] = crossing.roads
  return (
    <article className="flex flex-col rounded-lg border border-border bg-card p-4">
      <Header rank={rank} total={crossing.n} />
      <h3 className="mt-2 font-semibold leading-tight">{a}</h3>
      <div className="text-sm text-muted-foreground">and {b}</div>
      <WeekBars
        weeks={crossing.weeks.slice(range.first)}
        first={range.first}
        max={weekMax}
        flags={range.flags}
        since={since}
        noun="entries"
      />
      <ShowOnMap id={crossing.id} onShow={onShow} />
    </article>
  )
}
