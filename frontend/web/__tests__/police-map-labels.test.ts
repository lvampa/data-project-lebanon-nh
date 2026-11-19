import { describe, expect, it } from 'vitest'
import { plainOutcome, plainType } from '@/lib/police-map/labels'

describe('plainType', () => {
  it('puts a dispatch code in plain words', () => {
    expect(plainType('Motor Vehicle Stop')).toBe('Traffic stop')
    expect(plainType('BUSINESS CHECK - CLOSED')).toBe('Business check, after hours')
    expect(plainType('911 Hang-Ups/Abandoned Calls')).toBe('911 hang-up')
  })

  it('ignores the case of the log', () => {
    expect(plainType('welfare check')).toBe('Welfare check')
  })

  it('keeps the log words for a type with no plain label, capitalizing only the first letter', () => {
    expect(plainType('LARCENY FROM VEHICLE')).toBe('Larceny from vehicle')
  })

  it('says unknown for no type', () => {
    expect(plainType(null)).toBe('Unknown')
  })
})

describe('plainOutcome', () => {
  it('gives a label and what it means', () => {
    expect(plainOutcome('Services Rendered')).toEqual({
      label: 'Help given',
      hint: 'Police gave help or assistance',
    })
    expect(plainOutcome('Incident Report Taken').label).toBe('Report filed')
    expect(plainOutcome('Report Taken').label).toBe('Report filed')
  })

  it('names a false alarm', () => {
    expect(plainOutcome('False Alarm').label).toBe('False alarm')
  })

  it('keeps the log word for an outcome with no plain label', () => {
    expect(plainOutcome('Referred to Prosecutor')).toEqual({
      label: 'Referred to Prosecutor',
      hint: null,
    })
  })

  it('says so when there is no outcome', () => {
    expect(plainOutcome(null).label).toBe('Not recorded')
  })
})
