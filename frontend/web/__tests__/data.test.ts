import { describe, it, expect, vi, afterEach } from 'vitest'
import fs from 'fs'

vi.mock('fs', () => ({
  default: {
    readFileSync: vi.fn(),
  },
  readFileSync: vi.fn(),
}))

afterEach(() => vi.restoreAllMocks())

describe('readDataFile', () => {
  it('reads and parses JSON from public/data/', async () => {
    vi.mocked(fs.readFileSync).mockReturnValueOnce(JSON.stringify({ total: 42 }))
    const { readDataFile } = await import('@/lib/data')
    const result = readDataFile<{ total: number }>('stats.json')
    expect(result.total).toBe(42)
    expect(vi.mocked(fs.readFileSync)).toHaveBeenCalledWith(
      expect.stringContaining('stats.json'),
      'utf8',
    )
  })

  it('throws when file is missing', async () => {
    vi.mocked(fs.readFileSync).mockImplementationOnce(() => {
      throw new Error('ENOENT')
    })
    const { readDataFile } = await import('@/lib/data')
    expect(() => readDataFile('missing.json')).toThrow('ENOENT')
  })
})
