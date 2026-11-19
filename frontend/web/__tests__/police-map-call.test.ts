import { clockOf } from '@/lib/police-map/format'
import { describe, expect, it } from 'vitest'
import { callTiming, channelLabel, minutesBetween, shortName } from '@/lib/police-map/call'

describe('channelLabel', () => {
  it('puts the channel in plain words', () => {
    expect(channelLabel('Telephone')).toBe('Reported by phone')
    expect(channelLabel('911')).toBe('Reported by 911')
    expect(channelLabel('Walk-In')).toBe('Reported in person')
    expect(channelLabel('Initiated')).toBe('Officer-initiated')
    expect(channelLabel('Alarm System')).toBe('Reported by an alarm')
  })

  it('falls back to the log word, and says so when there is none', () => {
    expect(channelLabel('Fax')).toBe('Reported by fax')
    expect(channelLabel(null)).toBe('How it came in was not recorded')
  })
})

describe('shortName', () => {
  it('shortens the first name to an initial', () => {
    expect(shortName('Christopher Day')).toBe('C. Day')
    expect(shortName('Mary Ann Smith')).toBe('M. Ann Smith')
  })

  it('keeps a name that is already short, or has one word', () => {
    expect(shortName('C. Day')).toBe('C. Day')
    expect(shortName('Day')).toBe('Day')
  })

  it('says nothing for no name', () => {
    expect(shortName(null)).toBeNull()
    expect(shortName('  ')).toBeNull()
  })
})

describe('minutesBetween', () => {
  it('counts whole minutes', () => {
    expect(minutesBetween('2026-06-01T12:00:00', '2026-06-01T12:07:00')).toBe(7)
  })

  it('skips a missing or backward time', () => {
    expect(minutesBetween(null, '2026-06-01T12:07:00')).toBeNull()
    expect(minutesBetween('2026-06-01T12:00:00', null)).toBeNull()
    expect(minutesBetween('2026-06-01T12:10:00', '2026-06-01T12:07:00')).toBeNull()
  })

  it('keeps zero', () => {
    expect(minutesBetween('2026-06-01T12:00:00', '2026-06-01T12:00:00')).toBe(0)
  })
})

describe('callTiming', () => {
  it('measures the arrival from the report and the time on scene from the arrival', () => {
    expect(
      callTiming({
        reported_at: '2026-06-01T12:00:00',
        arrived_at: '2026-06-01T12:09:00',
        cleared_at: '2026-06-01T12:40:00',
      }),
    ).toEqual({ arrivedAfter: 9, onScene: 31 })
  })

  it('leaves out what is missing', () => {
    expect(
      callTiming({ reported_at: '2026-06-01T12:00:00', arrived_at: null, cleared_at: null }),
    ).toEqual({ arrivedAfter: null, onScene: null })
  })
})

describe('clockOf', () => {
  it('reads the logged time without a zone shift', () => {
    expect(clockOf('2026-06-01T14:05:00')).toBe('2:05 pm')
    expect(clockOf('2026-06-01T00:30:00')).toBe('12:30 am')
  })

  it('is null when the step was not recorded', () => {
    expect(clockOf(null)).toBeNull()
  })
})
