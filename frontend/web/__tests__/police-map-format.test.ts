import { describe, expect, it } from 'vitest'
import { callWord, nameOf, streetOf, updatedLabel, windowLabel } from '@/lib/police-map/format'

describe('callWord', () => {
  it('says call for one and calls for the rest', () => {
    expect(callWord(1)).toBe('1 call')
    expect(callWord(0)).toBe('0 calls')
    expect(callWord(1234)).toBe('1,234 calls')
  })
})

describe('nameOf and streetOf', () => {
  it('split a place into its name and its street', () => {
    expect(nameOf('Lebanon Ford, 90 Miracle Mile')).toBe('Lebanon Ford')
    expect(streetOf('Lebanon Ford, 90 Miracle Mile')).toBe('90 Miracle Mile')
  })

  it('give a road no street', () => {
    expect(nameOf('Miracle Mile')).toBe('Miracle Mile')
    expect(streetOf('Miracle Mile')).toBeNull()
  })
})

describe('windowLabel', () => {
  it('runs from the start month to the month it was generated', () => {
    expect(windowLabel('2026-01-01', '2026-11-19T21:00:00Z')).toBe('Jan to Nov 2026')
  })

  it('names one month once', () => {
    expect(windowLabel('2026-01-01', '2026-01-20T12:00:00Z')).toBe('Jan 2026')
  })

  it('names both years across a year end', () => {
    expect(windowLabel('2026-01-01', '2027-02-03T12:00:00Z')).toBe('Jan 2026 to Feb 2027')
  })

  it('uses the date in New Hampshire, not in UTC', () => {
    // 1 am UTC on December 1 is still the evening of November 30 in Lebanon.
    expect(windowLabel('2026-01-01', '2026-12-01T01:00:00Z')).toBe('Jan to Nov 2026')
  })
})

describe('updatedLabel', () => {
  it('is a short date', () => {
    expect(updatedLabel('2026-11-19T21:00:00Z')).toBe('Nov 19, 2026')
  })
})
