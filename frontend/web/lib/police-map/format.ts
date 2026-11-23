const NEW_HAMPSHIRE = 'America/New_York'
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

// Officers start about half the entries themselves, so a count is of log entries, not calls.
// A filter names its own kind, as the count line does: "54 traffic stops and calls".
const ONE_OF: Record<string, string> = {
  'log entries': 'log entry',
  'entries about a place': 'entry about a place',
  'traffic stops and calls': 'traffic stop or call',
  alarms: 'alarm',
}

export function entryWord(count: number, noun = 'log entries'): string {
  const word = count === 1 ? (ONE_OF[noun] ?? noun) : noun
  return `${count.toLocaleString('en-US')} ${word}`
}

// "Lebanon Ford" from "Lebanon Ford, 90 Miracle Mile".
export function nameOf(name: string): string {
  return name.split(', ')[0]
}

// "90 Miracle Mile" from "Lebanon Ford, 90 Miracle Mile", and null for a road.
export function streetOf(name: string): string | null {
  const rest = name.split(', ').slice(1).join(', ')
  return rest === '' ? null : rest
}

function inNewHampshire(iso: string, options: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat('en-US', { timeZone: NEW_HAMPSHIRE, ...options }).format(
    new Date(iso),
  )
}

// "January 1, 2026" from "2026-01-01".
export function sinceLabel(since: string): string {
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'UTC',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  }).format(new Date(`${since}T00:00:00Z`))
}

// A place whose own calls are none has only the traffic on its street to show.
export function trafficNearby(count: number): string {
  const what = count === 1 ? 'traffic stop or call' : 'traffic stops and calls'
  return `${count.toLocaleString('en-US')} ${what} nearby`
}

// The line under an approximate place's name.
export function approximateLine(street: string | null): string {
  return street ? `Approximate location, somewhere on ${street}` : 'Approximate location'
}

// "389 at the street itself · 313 at 19 places on it", under a street's total.
export function streetBreakdown(own: number, onStreet: { count: number }[]): string {
  const theirs = onStreet.reduce((sum, place) => sum + place.count, 0)
  const places = onStreet.length === 1 ? '1 place' : `${onStreet.length} places`
  return `${own.toLocaleString('en-US')} at the street itself · ${theirs.toLocaleString('en-US')} at ${places} on it`
}

// Under a Places card: its alarms, none of which the card counts. "3 alarms, 1 false, not
// counted above".
export function alarmsLine(alarms: number, falseAlarms: number): string {
  const noun = alarms === 1 ? 'alarm' : 'alarms'
  const falseNote = falseAlarms > 0 ? `, ${falseAlarms.toLocaleString('en-US')} false` : ''
  return `${alarms.toLocaleString('en-US')} ${noun}${falseNote}, not counted above`
}

// Under a place's filtered count: the calls from the public, which is the number its Places
// card shows, and the entries officers started. Both are counted; the rest is neither.
export function whoStartedLine(fromPublic: number, byOfficers: number): string {
  const calls =
    fromPublic === 1 ? '1 was a call' : `${fromPublic.toLocaleString('en-US')} were calls`
  const started = byOfficers === 1 ? '1 was' : `${byOfficers.toLocaleString('en-US')} were`
  return `${calls} from the public and ${started} started by officers.`
}

export const STATION_NOTE =
  'The Places tab leaves out the station, since the log files reports taken there under the station.'

// Over a street card's lists, which cover the street itself, and the whole year, never the
// places on it or a filter.
export function streetItselfLine(own: number): string {
  return `These lists cover the street itself, the whole year: ${own.toLocaleString('en-US')} ${own === 1 ? 'entry' : 'entries'}.`
}

// The heading over the places listed on a street's card.
export function onStreetHeading(street: string): string {
  return `On ${street}, exact spot unknown`
}

export const APPROXIMATE_TIP = 'approximate location'

// What a group of pins holds, for its tooltip. A group with no calls of its own has only
// traffic, and its weight is exactly the sum of that traffic.
const TRAFFIC = 'traffic stops and calls'

export function clusterHolds(calls: number, weight: number, noun?: string): string {
  // Under the traffic filter, a group's traffic is what it holds, as its size shows.
  if (noun === TRAFFIC) return entryWord(weight, noun)
  return calls === 0 ? trafficNearby(weight) : entryWord(calls, noun)
}

// "Jan to Nov 2026" for a window that starts in January 2026 and was generated in November.
export function windowLabel(since: string, generatedAt: string): string {
  const [year, month] = since.split('-').map(Number)
  const start = MONTHS[month - 1]
  const endYear = Number(inNewHampshire(generatedAt, { year: 'numeric' }))
  const end = inNewHampshire(generatedAt, { month: 'short' })
  if (endYear === year) return start === end ? `${start} ${year}` : `${start} to ${end} ${year}`
  return `${start} ${year} to ${end} ${endYear}`
}

// A call's time as the log printed it, in Lebanon's own time: "Nov 18, 2:05 pm". The log has
// no zone, so the text is read as it is and never shifted.
export function formatCallTime(reportedAt: string | null): string {
  const match = reportedAt?.match(/^\d{4}-(\d{2})-(\d{2})T/)
  const clock = clockOf(reportedAt)
  if (!match || !clock) return 'Time not recorded'
  return `${MONTHS[Number(match[1]) - 1]} ${Number(match[2])}, ${clock}`
}

// "2:05 pm" from a logged timestamp, or null when the step was not recorded.
export function clockOf(timestamp: string | null): string | null {
  const match = timestamp?.match(/T(\d{2}):(\d{2})/)
  if (!match) return null
  const h = Number(match[1])
  return `${h % 12 === 0 ? 12 : h % 12}:${match[2]} ${h < 12 ? 'am' : 'pm'}`
}

// "Nov 19, 2026"
export function updatedLabel(generatedAt: string): string {
  return inNewHampshire(generatedAt, { month: 'short', day: 'numeric', year: 'numeric' })
}
