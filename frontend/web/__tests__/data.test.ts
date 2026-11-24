import { describe, it, expect, vi, afterEach } from 'vitest'

afterEach(() => {
  vi.unstubAllEnvs()
  vi.resetModules()
})

describe('dataUrl', () => {
  it('serves from /data by default', async () => {
    const { dataUrl } = await import('@/lib/data')
    expect(dataUrl('stats.json')).toBe('/data/stats.json')
  })

  it('uses NEXT_PUBLIC_DATA_URL and drops a trailing slash', async () => {
    vi.stubEnv('NEXT_PUBLIC_DATA_URL', 'https://data.example.test/releases/')
    const { dataUrl } = await import('@/lib/data')
    expect(dataUrl('stats.json')).toBe('https://data.example.test/releases/stats.json')
  })
})
