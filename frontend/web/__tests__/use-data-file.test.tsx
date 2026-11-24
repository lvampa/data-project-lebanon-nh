import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { DataStatus } from '@/components/data-status'
import { clearDataFileCache, useDataFile } from '@/components/use-data-file'

function Probe() {
  const file = useDataFile<{ total: number }>('stats.json')
  if (file.status !== 'ready') return <DataStatus states={[file]} />
  return <p>total {file.data.total}</p>
}

function TwoFiles() {
  const first = useDataFile<number>('a.json')
  const second = useDataFile<number>('b.json')
  if (first.status !== 'ready' || second.status !== 'ready') {
    return <DataStatus states={[first, second]} />
  }
  return <p>both ready</p>
}

function ok(body: unknown) {
  return { ok: true, json: () => Promise.resolve(body) }
}

afterEach(() => {
  vi.unstubAllGlobals()
  clearDataFileCache()
})

describe('useDataFile', () => {
  it('shows loading, then the data', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok({ total: 42 })))
    render(<Probe />)
    expect(screen.getByRole('status')).toBeInTheDocument()
    expect(await screen.findByText('total 42')).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith('/data/stats.json', expect.anything())
  })

  it('announces a failed response, and Try again fetches again', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 404 })
      .mockResolvedValueOnce(ok({ total: 7 }))
    vi.stubGlobal('fetch', fetchMock)
    render(<Probe />)
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /try again/i }))
    await waitFor(() => expect(screen.getByText('total 7')).toBeInTheDocument())
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('retries every failed file with one click', async () => {
    let healed = false
    const fetchMock = vi.fn((url: string) =>
      Promise.resolve(healed ? ok(url.length) : { ok: false, status: 500 }),
    )
    vi.stubGlobal('fetch', fetchMock)
    render(<TwoFiles />)
    const retry = await screen.findByRole('button', { name: /try again/i })
    healed = true
    fireEvent.click(retry)
    expect(await screen.findByText('both ready')).toBeInTheDocument()
  })

  it('fetches a file once for two mounts', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(ok({ total: 1 })))
    const first = render(<Probe />)
    await screen.findByText('total 1')
    first.unmount()
    render(<Probe />)
    await screen.findByText('total 1')
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('aborts a file that is not shared when the caller unmounts', async () => {
    let signal: AbortSignal | undefined
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init: RequestInit) => {
        signal = init.signal ?? undefined
        return new Promise(() => {})
      }),
    )
    function Unshared() {
      useDataFile<number>('places/a.json', { shared: false })
      return null
    }
    const view = render(<Unshared />)
    view.unmount()
    expect(signal?.aborted).toBe(true)
  })
})
