import { describe, it, expect } from 'vitest'
import { formatTypeData, formatWeekdayData } from '@/lib/chart-utils'
import type { TypeStat, WeekdayStat } from '@/lib/types'

describe('formatTypeData', () => {
  it('slices to the requested limit', () => {
    const input: TypeStat[] = [
      { incident_type: 'THEFT', count: 10 },
      { incident_type: 'TRAFFIC', count: 5 },
      { incident_type: 'OTHER', count: 1 },
    ]
    const result = formatTypeData(input, 2)
    expect(result).toHaveLength(2)
    expect(result[0]).toEqual({ name: 'THEFT', count: 10 })
  })

  it('returns empty array for empty input', () => {
    expect(formatTypeData([], 10)).toEqual([])
  })
})

describe('formatWeekdayData', () => {
  it('returns all 7 days in Sun–Sat order', () => {
    const input: WeekdayStat[] = [
      { day: 'Fri', count: 20 },
      { day: 'Sun', count: 5 },
      { day: 'Mon', count: 15 },
    ]
    const result = formatWeekdayData(input)
    expect(result.map((r) => r.day)).toEqual(['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'])
  })

  it('fills missing days with count 0', () => {
    const result = formatWeekdayData([{ day: 'Wed', count: 8 }])
    expect(result).toHaveLength(7)
    expect(result.find((r) => r.day === 'Sun')?.count).toBe(0)
    expect(result.find((r) => r.day === 'Wed')?.count).toBe(8)
  })
})
