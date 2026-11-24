import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { DataStatus } from '@/components/data-status'
import { useDataFile } from '@/components/use-data-file'

function Probe() {
  const file = useDataFile<{ total: number }>('stats.json')
  if (file.status !== 'ready') return <DataStatus states={[file]} />
  return <p>total {file.data.total}</p>
}

afterEach(() => vi.restoreAllMocks())

describe('useDataFile', () => {
  it('shows loading, then the data', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ total: 42 }) }),
    )
    render(<Probe />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading')
    expect(await screen.findByText('total 42')).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith('/data/stats.json', expect.anything())
  })

  it('shows an error on a failed response, and Try again fetches again', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 404 })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ total: 7 }) })
    vi.stubGlobal('fetch', fetchMock)
    render(<Probe />)
    fireEvent.click(await screen.findByRole('button', { name: /try again/i }))
    await waitFor(() => expect(screen.getByText('total 7')).toBeInTheDocument())
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
