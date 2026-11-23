'use client'
import { useEffect, useState } from 'react'
import { categoryOf } from '@/lib/police-map/categories'
import {
  DEFAULT_FILTERS,
  KINDS,
  RANGES,
  TIMES,
  isDefault,
  sheetFilterCount,
  type Filters,
} from '@/lib/police-views/filters'

interface Props {
  filters: Filters
  onChange: (filters: Filters) => void
  // The count line, such as "1,204 of 19,316 log entries", or null while loading.
  count: string | null
  // Places has one fixed lens, so it shows what it counts instead of the kind chips.
  lens: string | null
  // On the Officers tab every officer shows, so the officer filter steps aside.
  showOfficer: boolean
}

const CHIP =
  'inline-flex h-9 shrink-0 items-center gap-2 whitespace-nowrap rounded-full border border-input bg-card px-3.5 text-sm font-medium hover:border-ring aria-pressed:border-primary aria-pressed:bg-primary aria-pressed:text-primary-foreground'
const SELECT =
  'h-9 rounded-lg border border-input bg-card px-2.5 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-3 focus:ring-ring/25'

export function FilterBar({ filters, onChange, count, lens, showOfficer }: Props) {
  const [sheetOpen, setSheetOpen] = useState(false)
  const set = (change: Partial<Filters>) => onChange({ ...filters, ...change })
  const hidden = sheetFilterCount(filters)

  const selects = (
    <>
      <select
        aria-label="Time of day"
        className={SELECT}
        value={filters.time}
        onChange={(event) => set({ time: event.target.value as Filters['time'] })}
      >
        {TIMES.map((time) => (
          <option key={time.id} value={time.id}>
            {time.label}
          </option>
        ))}
      </select>
      <select
        aria-label="Dates"
        className={SELECT}
        value={filters.range}
        onChange={(event) => set({ range: event.target.value as Filters['range'] })}
      >
        {RANGES.map((range) => (
          <option key={range.id} value={range.id}>
            {range.label}
          </option>
        ))}
      </select>
    </>
  )

  return (
    <div className="mb-3.5 flex flex-wrap items-center gap-x-4 gap-y-2.5">
      {lens ? (
        <p className="text-sm text-muted-foreground">{lens}</p>
      ) : (
        <div
          role="group"
          aria-label="Kind of activity"
          className="-my-1 flex min-w-0 flex-1 gap-1.5 overflow-x-auto py-1 md:flex-none"
        >
          {KINDS.map((kind) => (
            <button
              key={kind.id}
              type="button"
              aria-pressed={filters.kind === kind.id}
              onClick={() => set({ kind: kind.id })}
              className={CHIP}
            >
              {kind.category && (
                <span
                  aria-hidden
                  className="size-2 rounded-full ring-2 ring-card"
                  style={{ background: categoryOf(kind.category).color }}
                />
              )}
              {kind.label}
            </button>
          ))}
        </div>
      )}

      <div className="hidden flex-wrap gap-2 md:flex">{selects}</div>

      {showOfficer && filters.officer && (
        <span className="inline-flex h-9 items-center gap-1 rounded-full bg-secondary pl-3.5 pr-1 text-sm font-medium">
          Officer: {filters.officer}
          <button
            type="button"
            aria-label="Show every officer"
            onClick={() => set({ officer: null })}
            className="size-7 rounded-full text-base text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            ×
          </button>
        </span>
      )}

      <button type="button" onClick={() => setSheetOpen(true)} className={`${CHIP} md:hidden`}>
        {hidden ? `Filters (${hidden})` : 'Filters'}
      </button>

      <div className="flex w-full items-center gap-3 text-sm text-muted-foreground md:ml-auto md:w-auto">
        {count && <span className="tabular-nums">{count}</span>}
        {!isDefault(filters) && (
          <button
            type="button"
            onClick={() => onChange(DEFAULT_FILTERS)}
            className="font-medium text-primary hover:underline"
          >
            Clear filters
          </button>
        )}
      </div>

      {sheetOpen && (
        <FilterSheet
          onClose={() => setSheetOpen(false)}
          onClear={() => onChange({ ...DEFAULT_FILTERS, kind: filters.kind })}
          count={count}
        >
          {selects}
        </FilterSheet>
      )}
    </div>
  )
}

// The filters a phone has no room for, in a sheet from the bottom of the screen.
function FilterSheet({
  onClose,
  onClear,
  count,
  children,
}: {
  onClose: () => void
  onClear: () => void
  count: string | null
  children: React.ReactNode
}) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 md:hidden">
      <div className="absolute inset-0 bg-foreground/40" onClick={onClose} aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Filters"
        className="absolute inset-x-0 bottom-0 grid gap-3.5 rounded-t-2xl bg-background px-4 pb-[calc(1rem+env(safe-area-inset-bottom))] pt-5 [&_select]:h-11 [&_select]:w-full [&_select]:text-base"
      >
        <h2 className="text-display-3">Filters</h2>
        {children}
        <div className="grid grid-cols-[1fr_2fr] gap-2.5">
          <button
            type="button"
            onClick={onClear}
            className="h-12 rounded-full border border-input bg-card font-semibold"
          >
            Clear
          </button>
          <button
            type="button"
            onClick={onClose}
            className="h-12 rounded-full bg-primary font-semibold text-primary-foreground"
          >
            {count ? `Show ${count}` : 'Done'}
          </button>
        </div>
      </div>
    </div>
  )
}
