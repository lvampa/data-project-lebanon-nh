'use client'
import { useId, useMemo, useState, type KeyboardEvent } from 'react'
import { nameOf } from '@/lib/police-map/format'
import { pinName } from '@/lib/police-map/map-style'
import { searchPlaces } from '@/lib/police-map/search'
import type { Address } from '@/lib/types'

interface Props {
  addresses: Address[]
  onChoose: (id: string) => void
}

// A box over the map that finds a place or a street by name.
export function PlaceSearch({ addresses, onChoose }: Props) {
  const listId = useId()
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const matches = useMemo(() => searchPlaces(addresses, query), [addresses, query])
  const showing = open && matches.length > 0

  const choose = (place: Address) => {
    setOpen(false)
    setQuery(nameOf(pinName(place)))
    onChoose(place.id)
  }

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') {
      // A closed list opens on the first press, and moves on the next.
      if (!showing) setOpen(true)
      else setActive((i) => Math.min(i + 1, matches.length - 1))
      event.preventDefault()
    } else if (event.key === 'ArrowUp') {
      setActive((i) => Math.max(i - 1, 0))
      event.preventDefault()
    } else if (event.key === 'Enter' && showing) {
      choose(matches[Math.min(active, matches.length - 1)])
    } else if (event.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className="w-80 max-w-full">
      <input
        type="search"
        role="combobox"
        aria-expanded={showing}
        aria-autocomplete="list"
        aria-controls={listId}
        aria-activedescendant={showing ? `${listId}-${active}` : undefined}
        aria-label="Search a place or street"
        placeholder="Search a place or street"
        autoComplete="off"
        value={query}
        onChange={(event) => {
          setQuery(event.target.value)
          setActive(0)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
        className="h-10 w-full rounded-lg border border-input bg-card px-3.5 text-sm text-foreground shadow-sm focus:border-ring focus:outline-none focus:ring-3 focus:ring-ring/25"
      />
      {showing && (
        <ul
          id={listId}
          role="listbox"
          className="mt-1.5 max-h-72 overflow-auto rounded-lg border border-border bg-card p-1 shadow-md"
        >
          {matches.map((place, i) => (
            <li
              key={place.id}
              id={`${listId}-${i}`}
              role="option"
              aria-selected={i === active}
              // Choosing on mousedown, before the input loses focus and closes the list.
              onMouseDown={(event) => {
                event.preventDefault()
                choose(place)
              }}
              onMouseEnter={() => setActive(i)}
              className="flex cursor-pointer justify-between gap-2 rounded-md px-2.5 py-1.5 text-sm aria-selected:bg-secondary"
            >
              {pinName(place)}
              <span className="font-mono text-xs text-muted-foreground">
                {place.count.toLocaleString('en-US')}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
