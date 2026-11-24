'use client'
import { useEffect, useState } from 'react'
import { fetchDataFile } from '@/lib/data'

// `reload` fetches the file again, for a caller that finds it unusable after it arrived.
export type DataState<T> =
  | { status: 'loading' }
  | { status: 'error'; retry: () => void }
  | { status: 'ready'; data: T; reload: () => void }

// Each file is fetched once per page load, so moving between pages does not download and parse
// it again. A failed fetch is dropped, so Try again asks the host again.
const loads = new Map<string, Promise<unknown>>()

function loadOnce<T>(filename: string): Promise<T> {
  let load = loads.get(filename) as Promise<T> | undefined
  if (!load) {
    // The load is shared, so no single page's unmount can abort it.
    load = fetchDataFile<T>(filename)
    loads.set(filename, load)
    load.catch(() => loads.delete(filename))
  }
  return load
}

export function clearDataFileCache(): void {
  loads.clear()
}

// One exported JSON file, fetched in the browser when the page mounts. A null filename fetches
// nothing and stays loading. A file with `shared: false` is not kept, and its fetch is aborted
// when the caller moves on, which suits many small files such as place cards.
export function useDataFile<T>(
  filename: string | null,
  { shared = true }: { shared?: boolean } = {},
): DataState<T> {
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
    const controller = shared ? null : new AbortController()
    const load = controller ? fetchDataFile<T>(filename, controller.signal) : loadOnce<T>(filename)
    load
      .then((data) => current && setResult({ key, value: { ok: true, data } }))
      .catch(() => current && setResult({ key, value: { ok: false } }))
    return () => {
      current = false
      controller?.abort()
    }
  }, [filename, key, shared])

  if (result?.key !== key) return { status: 'loading' }
  const reload = () => {
    if (filename !== null) loads.delete(filename)
    setAttempt((n) => n + 1)
  }
  if (!result.value.ok) return { status: 'error', retry: reload }
  return { status: 'ready', data: result.value.data, reload }
}
