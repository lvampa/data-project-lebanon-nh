'use client'
import { useEffect, useState } from 'react'
import { dataUrl, fetchJson } from '@/lib/data'

export type DataState<T> =
  { status: 'loading' } | { status: 'error'; retry: () => void } | { status: 'ready'; data: T }

// One exported JSON file, fetched in the browser when the page mounts.
export function useDataFile<T>(filename: string): DataState<T> {
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState<{
    key: string
    value: { ok: true; data: T } | { ok: false }
  } | null>(null)

  // A new attempt is a new key, so Try again shows loading until the fetch ends.
  const key = `${filename}:${attempt}`

  useEffect(() => {
    const controller = new AbortController()
    fetchJson<T>(dataUrl(filename), controller.signal)
      .then((data) => setResult({ key, value: { ok: true, data } }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setResult({ key, value: { ok: false } })
      })
    return () => controller.abort()
  }, [filename, key])

  if (result?.key !== key) return { status: 'loading' }
  if (!result.value.ok) return { status: 'error', retry: () => setAttempt((n) => n + 1) }
  return { status: 'ready', data: result.value.data }
}
