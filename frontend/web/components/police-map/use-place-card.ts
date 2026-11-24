'use client'
import { useDataFile, type DataState } from '@/components/use-data-file'
import { placeFile } from '@/lib/data'
import type { PlaceCard } from '@/lib/types'

// The card for one pin, fetched when the pin is chosen. Choosing another pin shows loading
// until its card arrives.
export function usePlaceCard(id: string | null): DataState<PlaceCard> | null {
  const file = useDataFile<PlaceCard>(id ? placeFile(id) : null, { shared: false })
  return id ? file : null
}
