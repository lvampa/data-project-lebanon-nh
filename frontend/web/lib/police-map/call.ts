// What a call row says about one call: how it came in, who answered, how long it took.

const CHANNELS: Record<string, string> = {
  Telephone: 'Reported by phone',
  '911': 'Reported by 911',
  'Walk-In': 'Reported in person',
  Initiated: 'Started by an officer',
  'Alarm System': 'Reported by an alarm',
  Radio: 'Reported by radio',
  'E-Mail': 'Reported by email',
}

export function channelLabel(callSource: string | null): string {
  if (!callSource) return 'How it came in was not recorded'
  return CHANNELS[callSource] ?? `Reported by ${callSource.toLowerCase()}`
}

// "Christopher Day" becomes "C. Day". A name already shortened to an initial stays as it is.
export function shortName(full: string | null): string | null {
  const parts = full?.trim().split(/\s+/) ?? []
  if (parts.length === 0 || parts[0] === '') return null
  if (parts.length === 1 || /^\w\.?$/.test(parts[0])) return parts.join(' ')
  return `${parts[0][0]}. ${parts.slice(1).join(' ')}`
}

// Whole minutes from one logged time to the next, or null when either is missing or the
// clock runs backward, which a log typo can cause.
export function minutesBetween(from: string | null, to: string | null): number | null {
  if (!from || !to) return null
  const minutes = (Date.parse(`${to}Z`) - Date.parse(`${from}Z`)) / 60000
  return Number.isNaN(minutes) || minutes < 0 ? null : Math.round(minutes)
}

export interface CallTiming {
  arrivedAfter: number | null
  onScene: number | null
}

export function callTiming(call: {
  reported_at: string | null
  arrived_at: string | null
  cleared_at: string | null
}): CallTiming {
  return {
    arrivedAfter: minutesBetween(call.reported_at, call.arrived_at),
    onScene: minutesBetween(call.arrived_at, call.cleared_at),
  }
}
