import { describe, it, expect, vi, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { clearDataFileCache } from '@/components/use-data-file'
import { useActivity } from '@/components/police-views/use-activity'

vi.mock('@/lib/police-views/activity', () => ({
  decodeActivity: vi.fn(() => {
    throw new Error('unreadable')
  }),
}))

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
  clearDataFileCache()
})

describe('useActivity', () => {
  it('reports an error, not a throw, when the file cannot be decoded', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve({ pins: [] }) }),
    )
    const { result } = renderHook(() => useActivity([], true))
    await waitFor(() => expect(result.current.status).toBe('error'))
  })

  it('stays idle until a view asks for it', () => {
    vi.stubGlobal('fetch', vi.fn())
    const { result } = renderHook(() => useActivity([], false))
    expect(result.current.status).toBe('idle')
    expect(fetch).not.toHaveBeenCalled()
  })
})
