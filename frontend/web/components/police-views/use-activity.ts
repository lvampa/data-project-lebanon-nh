'use client'
import { useMemo, useState } from 'react'
import { useDataFile } from '@/components/use-data-file'
import { decodeActivity, type Activity, type ActivityFile } from '@/lib/police-views/activity'
import { DATA_FILES } from '@/lib/data'
import type { Address } from '@/lib/types'

export type ActivityState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; retry: () => void }
  | { status: 'ready'; activity: Activity }

// activity.json, fetched the first time a view asks for it, so the default map loads as fast
// as it did before the filters. Once asked, it stays asked, so going back to the default map
// keeps the data.
export function useActivity(addresses: Address[], wanted: boolean): ActivityState {
  const [asked, setAsked] = useState(wanted)
  if (wanted && !asked) setAsked(true)

  const file = useDataFile<ActivityFile>(asked ? DATA_FILES.activity : null)
  const data = file.status === 'ready' ? file.data : null
  const activity = useMemo(() => (data ? decodeActivity(data, addresses) : null), [data, addresses])

  if (!asked) return { status: 'idle' }
  if (file.status === 'error') return file
  return activity ? { status: 'ready', activity } : { status: 'loading' }
}
