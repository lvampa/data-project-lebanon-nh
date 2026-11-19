import { describe, expect, it } from 'vitest'
import { idFromHash } from '@/lib/police-map/hash'

const KNOWN = new Set(['lebanon-ford-90-miracle-mile', 'miracle-mile'])

describe('idFromHash', () => {
  it('finds a place that is on the map', () => {
    expect(idFromHash('#miracle-mile', KNOWN)).toBe('miracle-mile')
  })

  it('selects nothing for an unknown id, an empty hash or a broken one', () => {
    expect(idFromHash('#nowhere', KNOWN)).toBeNull()
    expect(idFromHash('', KNOWN)).toBeNull()
    expect(idFromHash('#%E0%A4%A', KNOWN)).toBeNull()
  })
})
