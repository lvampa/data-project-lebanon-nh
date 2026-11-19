'use client'
import { callWord, nameOf } from '@/lib/police-map/format'
import { pinName } from '@/lib/police-map/map-style'
import type { Address } from '@/lib/types'

interface Props {
  place: Address | undefined
  onClose: () => void
}

// The panel beside the map. The report card replaces the body of this.
export function SidePanel({ place, onClose }: Props) {
  if (!place) {
    return <p className="text-sm text-muted-foreground">Click a pin to see what happens there.</p>
  }
  return (
    <div>
      <div className="flex items-start justify-between gap-2">
        <h2 className="text-display-3">{nameOf(pinName(place))}</h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close and go back to the town summary"
          className="h-7 w-7 rounded-md border border-border text-lg leading-none text-muted-foreground hover:bg-secondary"
        >
          ×
        </button>
      </div>
      <p className="mt-2 text-sm text-muted-foreground">{callWord(place.count)}</p>
    </div>
  )
}
