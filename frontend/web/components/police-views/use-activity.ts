'use client'
import { useEffect, useState } from 'react'
import { decodeActivity, type Activity, type ActivityFile } from '@/lib/police-views/activity'
import { dataUrl } from '@/lib/data'
import type { Address } from '@/lib/types'

export type ActivityState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error' }
  | { status: 'ready'; activity: Activity }

// activity.json, fetched the first time a view asks for it, so the default map loads as fast
// as it did before the filters. Once asked, it stays asked, so going back to the default map
// keeps the data. A failed fetch is tried again on a new `attempt`.
export function useActivity(addresses: Address[], wanted: boolean, attempt = 0): ActivityState {
  const [asked, setAsked] = useState(wanted)
  const [state, setState] = useState<{ attempt: number; value: ActivityState } | null>(null)
  if (wanted && !asked) setAsked(true)

  useEffect(() => {
    if (!asked) return
    const controller = new AbortController()
    fetch(dataUrl('activity.json'), { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        return response.json() as Promise<ActivityFile>
      })
      .then((file) =>
        setState({
          attempt,
          value: { status: 'ready', activity: decodeActivity(file, addresses) },
        }),
      )
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setState({ attempt, value: { status: 'error' } })
      })
    return () => controller.abort()
  }, [asked, attempt, addresses])

  if (!asked) return { status: 'idle' }
  // Until this attempt's fetch ends, whatever is held belongs to an earlier one.
  return state?.attempt === attempt ? state.value : { status: 'loading' }
}
