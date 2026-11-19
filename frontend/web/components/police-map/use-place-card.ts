'use client'
import { useEffect, useState } from 'react'
import type { PlaceCard } from '@/lib/types'

export type CardState =
  { status: 'loading' } | { status: 'error' } | { status: 'ready'; card: PlaceCard }

// The card for one pin, fetched when the pin is chosen. A newer choice drops an older fetch.
export function usePlaceCard(id: string | null, attempt = 0): CardState | null {
  const [state, setState] = useState<{ id: string; value: CardState } | null>(null)

  useEffect(() => {
    if (!id) return
    const controller = new AbortController()
    fetch(`/data/places/${encodeURIComponent(id)}.json`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json() as Promise<PlaceCard>
      })
      .then((card) => setState({ id, value: { status: 'ready', card } }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setState({ id, value: { status: 'error' } })
      })
    return () => controller.abort()
  }, [id, attempt])

  if (!id) return null
  // Until this pin's card arrives, whatever is held belongs to another pin.
  return state?.id === id ? state.value : { status: 'loading' }
}
