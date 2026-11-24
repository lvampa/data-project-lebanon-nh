'use client'
import { useMemo, useState } from 'react'
import { useDataFile } from '@/components/use-data-file'
import { decodeActivity, type Activity, type ActivityFile } from '@/lib/police-views/activity'
import { DATA_FILES } from '@/lib/data'
import type { Address } from '@/lib/types'

function decodeOrFail(data: ActivityFile | null, addresses: Address[]): Activity | 'failed' | null {
  if (!data) return null
  try {
    return decodeActivity(data, addresses)
  } catch (error) {
    // eslint-disable-next-line no-console -- The only record of why the activity did not load.
    console.error(error)
    return 'failed'
  }
}

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
  const decoded = useMemo(() => decodeOrFail(data, addresses), [data, addresses])

  if (!asked) return { status: 'idle' }
  if (file.status === 'error') return file
  if (decoded === 'failed') {
    // A file the code cannot read, as with data from an older export, must not take the page down.
    return { status: 'error', retry: file.status === 'ready' ? file.reload : () => {} }
  }
  return decoded ? { status: 'ready', activity: decoded } : { status: 'loading' }
}
