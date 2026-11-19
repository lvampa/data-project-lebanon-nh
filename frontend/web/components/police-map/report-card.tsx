'use client'
import { useState } from 'react'
import { HowWeCount } from '@/components/police-map/how-we-count'
import { CallRow } from '@/components/police-map/call-row'
import { OutcomeLabel, TypeLabel } from '@/components/police-map/labels'
import type { CardState } from '@/components/police-map/use-place-card'
import { categoriesFor } from '@/lib/police-map/categories'
import { nameOf, streetOf } from '@/lib/police-map/format'
import { pinName } from '@/lib/police-map/map-style'
import { rankLine } from '@/lib/police-map/rank'
import type { Address, PlaceCard } from '@/lib/types'

interface Props {
  address: Address
  state: CardState
  // The call count of every pin, for the rank.
  counts: number[]
  year: string
  onClose: () => void
  onRetry: () => void
}

const SECTION_HEADING =
  'mb-2 mt-6 font-mono text-xs font-medium uppercase tracking-widest text-muted-foreground'
const ROW = 'flex justify-between gap-3 border-b border-border py-2 text-sm'
const ROW_VALUE = 'font-mono text-sm text-muted-foreground'

export function ReportCard({ address, state, counts, year, onClose, onRetry }: Props) {
  const road = address.kind === 'road'
  const name = pinName(address)
  const street = streetOf(name)

  return (
    <div>
      {/* 1. What this is */}
      <CardBar label={`${road ? 'Road' : 'Place'} · ${year}`} onClose={onClose} />
      <h2 className="text-display-3 mb-0.5 mt-1.5">{nameOf(name)}</h2>
      <div className="text-muted-foreground">{street ?? 'Road, highlighted on the map'}</div>

      {/* 2. How many, and how that compares */}
      <div className="mt-4 flex items-baseline gap-2.5">
        <b
          className="text-5xl font-semibold leading-none tabular-nums tracking-tight"
          style={{ fontFamily: 'var(--font-display)' }}
        >
          {address.count.toLocaleString('en-US')}
        </b>
        <span className="text-muted-foreground">
          {road ? 'calls on this road' : 'calls named this place'}
        </span>
      </div>
      <div className="mt-1.5 text-sm text-muted-foreground">{rankLine(address.count, counts)}</div>

      {state.status === 'loading' && (
        <p className="mt-6 text-sm text-muted-foreground">Loading the details…</p>
      )}
      {state.status === 'error' && (
        <div className="mt-6 rounded-lg border border-border bg-muted p-3 text-sm">
          <p>The details for this place did not load.</p>
          <button
            type="button"
            onClick={onRetry}
            className="mt-2 font-medium text-primary underline underline-offset-4"
          >
            Try again
          </button>
        </div>
      )}
      {state.status === 'ready' && (
        <CardDetails address={address} card={state.card} street={street} />
      )}

      {/* 7. Method */}
      <HowWeCount />
    </div>
  )
}

function CardBar({ label, onClose }: { label: string; onClose: () => void }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    await navigator.clipboard?.writeText(window.location.href)
    setCopied(true)
  }
  return (
    <div className="flex items-center justify-between gap-2">
      <div className="eyebrow">{label}</div>
      <div className="flex gap-1">
        <button
          type="button"
          onClick={copy}
          className="h-7 rounded-md border border-border bg-card px-2.5 text-xs font-medium text-muted-foreground hover:bg-secondary hover:text-foreground"
        >
          {copied ? 'Copied' : 'Copy link'}
        </button>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close and go back to the town summary"
          className="h-7 w-7 rounded-md border border-border bg-card text-lg leading-none text-muted-foreground hover:bg-secondary hover:text-foreground"
        >
          ×
        </button>
      </div>
    </div>
  )
}

function CardDetails({
  address,
  card,
  street,
}: {
  address: Address
  card: PlaceCard
  street: string | null
}) {
  const road = address.kind === 'road'
  const kinds = categoriesFor(address.kind, card.categories)
  const outcomes = card.outcomes.map(([disposition, n]) => ({ disposition, n }))
  if (card.false_alarms > 0 && !outcomes.some((o) => o.disposition === 'False Alarm')) {
    outcomes.push({ disposition: 'False Alarm', n: card.false_alarms })
  }

  return (
    <>
      {/* 3. What kinds of calls */}
      <div className="my-4 flex h-2.5 gap-0.5" role="img" aria-label="Calls by kind">
        {kinds.map((kind) => (
          <div
            key={kind.key}
            className="rounded"
            style={{ flex: card.categories[kind.key], background: kind.color }}
            title={`${kind.label}: ${card.categories[kind.key]}`}
          />
        ))}
      </div>
      {kinds.map((kind) => (
        <div key={kind.key} className={ROW}>
          <span>
            <span
              className="mr-2 inline-block h-2.5 w-2.5 rounded-sm align-middle"
              style={{ background: kind.color }}
            />
            {kind.label}
          </span>
          <span className={ROW_VALUE}>{card.categories[kind.key]}</span>
        </div>
      ))}
      {!road && address.traffic_count > 0 && (
        <p className="mt-3 border-l-4 border-highlight pl-3 text-sm text-muted-foreground">
          Also {address.traffic_count.toLocaleString('en-US')} traffic calls
          {street ? ` on ${street}` : ''}, highlighted on the map.
        </p>
      )}

      {/* 4. What happened */}
      {card.types.length > 0 && <h3 className={SECTION_HEADING}>What happened</h3>}
      {card.types.map(([type, n]) => (
        <div key={type} className={ROW}>
          <span>
            <TypeLabel type={type} />
          </span>
          <span className={ROW_VALUE}>{n}</span>
        </div>
      ))}

      {/* 5. How it ended */}
      {outcomes.length > 0 && <h3 className={SECTION_HEADING}>How it ended</h3>}
      {outcomes.map(({ disposition, n }) => (
        <div key={disposition} className={ROW}>
          <span>
            <OutcomeLabel disposition={disposition} />
          </span>
          <span className={ROW_VALUE}>{n}</span>
        </div>
      ))}

      {/* 6. The record itself */}
      {card.calls.length > 0 && (
        <>
          <h3 className={SECTION_HEADING}>Latest calls</h3>
          <ol>
            {card.calls.map((call) => (
              <CallRow key={call.case_number} call={call} />
            ))}
          </ol>
        </>
      )}
    </>
  )
}
