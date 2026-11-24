'use client'
import { useEffect, useState } from 'react'
import { dataUrl, fetchJson } from '@/lib/data'
import type { PlaceCard } from '@/lib/types'

export type CardState =
  { status: 'loading' } | { status: 'error' } | { status: 'ready'; card: PlaceCard }

// The card for one pin, fetched when the pin is chosen. A newer choice drops an older fetch.
export function usePlaceCard(id: string | null, attempt = 0): CardState | null {
  const [state, setState] = useState<{ key: string; value: CardState } | null>(null)

  // A new attempt is a new key, so Try again shows loading until the fetch ends.
  const key = `${id}:${attempt}`

  useEffect(() => {
    if (!id) return
    const controller = new AbortController()
    fetchJson<PlaceCard>(dataUrl(`places/${encodeURIComponent(id)}.json`), controller.signal)
      .then((card) => setState({ key, value: { status: 'ready', card } }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setState({ key, value: { status: 'error' } })
      })
    return () => controller.abort()
  }, [id, attempt, key])

  if (!id) return null
  // Until this pin's card arrives, whatever is held belongs to another pin.
  return state?.key === key ? state.value : { status: 'loading' }
}
