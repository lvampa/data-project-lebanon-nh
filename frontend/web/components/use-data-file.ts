'use client'
import { useEffect, useState } from 'react'
import { fetchDataFile } from '@/lib/data'

export type DataState<T> =
  { status: 'loading' } | { status: 'error'; retry: () => void } | { status: 'ready'; data: T }

// Each file is fetched once per page load, so moving between pages does not download and parse
// it again. A failed fetch is dropped, so Try again asks the host again.
const loads = new Map<string, Promise<unknown>>()

function loadOnce<T>(filename: string): Promise<T> {
  let load = loads.get(filename) as Promise<T> | undefined
  if (!load) {
    // The load is shared, so no single page's unmount can abort it.
    load = fetchDataFile<T>(filename, new AbortController().signal)
    loads.set(filename, load)
    load.catch(() => loads.delete(filename))
  }
  return load
}

export function clearDataFileCache(): void {
  loads.clear()
}

// One exported JSON file, fetched in the browser when the page mounts. A null filename fetches
// nothing and stays loading.
export function useDataFile<T>(filename: string | null): DataState<T> {
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState<{
    key: string
    value: { ok: true; data: T } | { ok: false }
  } | null>(null)

  // A new file or attempt is a new key, so the old result is never shown for it.
  const key = `${filename}:${attempt}`

  useEffect(() => {
    if (filename === null) return
    let current = true
    loadOnce<T>(filename)
      .then((data) => current && setResult({ key, value: { ok: true, data } }))
      .catch(() => current && setResult({ key, value: { ok: false } }))
    return () => {
      current = false
    }
  }, [filename, key])

  if (result?.key !== key) return { status: 'loading' }
  if (!result.value.ok) return { status: 'error', retry: () => setAttempt((n) => n + 1) }
  return { status: 'ready', data: result.value.data }
}
