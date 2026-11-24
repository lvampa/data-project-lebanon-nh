'use client'
import { useDataFile } from '@/components/use-data-file'
import { placeFile } from '@/lib/data'
import type { PlaceCard } from '@/lib/types'

export type CardState =
  { status: 'loading' } | { status: 'error' } | { status: 'ready'; card: PlaceCard }

// The card for one pin, fetched when the pin is chosen. Choosing another pin shows loading
// until its card arrives.
export function usePlaceCard(id: string | null): { state: CardState | null; retry: () => void } {
  const file = useDataFile<PlaceCard>(id ? placeFile(id) : null)
  const noRetry = () => {}
  if (!id) return { state: null, retry: noRetry }
  if (file.status === 'ready')
    return { state: { status: 'ready', card: file.data }, retry: noRetry }
  if (file.status === 'error') return { state: { status: 'error' }, retry: file.retry }
  return { state: { status: 'loading' }, retry: noRetry }
}
