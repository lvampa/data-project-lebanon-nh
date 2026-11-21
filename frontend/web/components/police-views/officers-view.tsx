'use client'
import { useMemo, useState } from 'react'
import { Tabs } from '@project/ui/components/ui/tabs'
import { TypeLabel } from '@/components/police-map/labels'
import type { Activity } from '@/lib/police-views/activity'
import { tally, topOf, typical, type Tally } from '@/lib/police-views/counts'
import { HourStrip } from './hour-strip'

interface Props {
  activity: Activity
  // The page's filters, without the officer filter, so every officer shows.
  kept: Uint8Array
  noun: string
  // "Jan to Nov 2026", for the line under the heading.
  rangeLabel: string
  onShow: (officer: string) => void
}

// An officer with fewer entries than this is more likely a log slip than a beat.
const MIN_ENTRIES = 25

type Sort = 'count' | 'name'

export function OfficersView({ activity, kept, noun, rangeLabel, onShow }: Props) {
  const [sort, setSort] = useState<Sort>('count')
  const unnamed = activity.officers.indexOf(null)
  const officers = useMemo(
    () =>
      tally(activity, kept, (i) => (activity.officer[i] === unnamed ? -1 : activity.officer[i])),
    [activity, kept, unnamed],
  )
  const leftOut = useMemo(() => {
    let n = 0
    for (let i = 0; i < activity.size; i++) if (kept[i] && activity.officer[i] === unnamed) n++
    return n
  }, [activity, kept, unnamed])

  const nameOf = (officer: number) => activity.officers[officer] ?? ''
  const shown = [...officers]
    .filter(([, t]) => t.n >= MIN_ENTRIES)
    .sort(([a, ta], [b, tb]) =>
      sort === 'name' ? nameOf(a).localeCompare(nameOf(b)) : tb.n - ta.n || a - b,
    )

  return (
    <section aria-labelledby="officers-heading">
      <div className="mb-3.5 flex flex-wrap items-end justify-between gap-2.5">
        <div>
          <h2 id="officers-heading" className="text-display-3">
            Who handled the activity
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {shown.length} officers with {MIN_ENTRIES} or more {noun} in {rangeLabel}.{' '}
            {leftOut > 0 &&
              `${leftOut.toLocaleString('en-US')} ${leftOut === 1 ? 'entry names' : 'entries name'} no officer and ${leftOut === 1 ? 'is' : 'are'} left out.`}
          </p>
        </div>
        <Tabs
          variant="pill"
          items={[
            { id: 'count', label: 'Most entries' },
            { id: 'name', label: 'A to Z' },
          ]}
          value={sort}
          onChange={(id) => setSort(id as Sort)}
        />
      </div>

      {shown.length === 0 ? (
        <p className="text-muted-foreground">
          No activity matches these filters. Try a wider date range.
        </p>
      ) : (
        <ol className="grid grid-cols-1 gap-3 sm:grid-cols-[repeat(auto-fill,minmax(270px,1fr))]">
          {shown.map(([officer, t]) => (
            <li key={officer} className="grid">
              <OfficerCard
                name={nameOf(officer)}
                tally={t}
                types={activity.types}
                onShow={onShow}
              />
            </li>
          ))}
        </ol>
      )}
      <p className="mt-3.5 text-sm text-muted-foreground">
        An officer who started an entry was on patrol, on a check or making a stop. One who was sent
        went because someone called. Time on scene runs from arrival to clearing.
      </p>
    </section>
  )
}

function OfficerCard({
  name,
  tally: t,
  types,
  onShow,
}: {
  name: string
  tally: Tally
  types: (string | null)[]
  onShow: (officer: string) => void
}) {
  const started = Math.round((100 * t.initiated) / t.n)
  const scene = typical(t.scenes)
  return (
    <article className="flex flex-col rounded-lg border border-border bg-card p-4">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="font-semibold leading-tight">{name}</h3>
        <b
          className="text-display-3 tabular-nums leading-none"
          style={{ fontFamily: 'var(--font-display)' }}
        >
          {t.n.toLocaleString('en-US')}
        </b>
      </div>
      <div
        className="mt-3 mb-1 flex h-2.5 gap-0.5 overflow-hidden rounded"
        role="img"
        aria-label={`${started}% started by the officer, ${100 - started}% sent`}
      >
        <i className="block" style={{ width: `${started}%`, background: 'var(--chart-1)' }} />
        <i className="block" style={{ width: `${100 - started}%`, background: 'var(--chart-4)' }} />
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{started}% started themselves</span>
        <span>{100 - started}% sent</span>
      </div>
      <h4 className="mt-3.5 mb-1.5 font-mono text-xs font-medium uppercase tracking-widest text-muted-foreground">
        When they work
      </h4>
      <HourStrip hours={t.hours} />
      <div className="mt-2.5 grid gap-0.5 text-sm text-muted-foreground">
        <span>
          Most often:{' '}
          {topOf(t.types, 3).map(([type], index) => (
            <b key={type} className="font-medium text-foreground">
              {index > 0 && ', '}
              <TypeLabel type={types[type]} />
            </b>
          ))}
        </span>
        {scene !== null && (
          <span>
            Typical time on scene: <b className="font-medium text-foreground">{scene} min</b>
          </span>
        )}
      </div>
      <button
        type="button"
        onClick={() => onShow(name)}
        className="mt-3 self-start text-sm font-medium text-primary hover:underline"
      >
        See on the map →
      </button>
    </article>
  )
}
