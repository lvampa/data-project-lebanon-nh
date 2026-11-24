import type { Address } from '@/lib/types'

export const ROADS_MODES = [
  { id: 'roads', label: 'Roads' },
  { id: 'crossings', label: 'Crossings' },
] as const
export type RoadsMode = (typeof ROADS_MODES)[number]['id']

// What the roll-up needs from a pin's tally: its entries, and how many fell in each week.
export interface PinCount {
  n: number
  weeks: number[]
}

export interface RoadCrossing {
  // The crossing's own pin.
  id: string
  // The other road.
  other: string
  n: number
}

export interface Road {
  name: string
  // The entries on the road's own pin, the bare road.
  own: number
  // The entries on its crossings, each counted again on the other road.
  atCrossings: number
  total: number
  weeks: number[]
  // Busiest first.
  crossings: RoadCrossing[]
  // The pin "Show on the map" opens: the bare road, or its busiest crossing.
  showId: string
}

export interface Crossing {
  id: string
  name: string
  roads: [string, string]
  n: number
  weeks: number[]
}

// Words that make a highway description, not a pair of roads: "I-89 at Exits 19 and 20".
const DESCRIBES_A_SPOT =
  /\b(exits?|near|at|between|toward|northbound|southbound|eastbound|westbound|nb|sb|mile marker)\b/i

// "Heater Rd and NH Route 120" is the crossing of those two roads. Anything that is not
// exactly two roads joined by "and" is a road of its own.
export function parseCrossing(name: string): [string, string] | null {
  const parts = name.split(' and ').map((part) => part.trim())
  if (parts.length !== 2 || parts.some((part) => part === '' || DESCRIBES_A_SPOT.test(part))) {
    return null
  }
  return [parts[0], parts[1]]
}

function addWeeks(into: number[], weeks: number[]): number[] {
  const sum =
    into.length >= weeks.length ? into : [...into, ...new Array(weeks.length - into.length).fill(0)]
  weeks.forEach((value, week) => (sum[week] += value))
  return sum
}

// A road's number is its own pin plus every crossing pin it is part of, so a crossing counts
// toward both of its roads. The places listed on a road are not in it. A pin with no entries
// is left out, as on the map. `counts` is keyed by index into `addresses`.
export function buildRoads(
  addresses: Address[],
  counts: Map<number, PinCount>,
): { roads: Road[]; crossings: Crossing[] } {
  const crossings: Crossing[] = []
  const bare = new Map<string, { id: string; n: number; weeks: number[] }>()

  addresses.forEach((address, index) => {
    const count = counts.get(index)
    if (address.kind !== 'road' || address.hidden || !count || count.n === 0) return
    const name = address.normalized_address ?? address.raw_address
    const roads = parseCrossing(name)
    if (roads) {
      crossings.push({ id: address.id, name, roads, n: count.n, weeks: count.weeks })
      return
    }
    const known = bare.get(name)
    bare.set(name, {
      // Two pins with one name are one road, shown on the busier.
      id: known && known.n >= count.n ? known.id : address.id,
      n: (known?.n ?? 0) + count.n,
      weeks: addWeeks(known?.weeks ?? [], count.weeks),
    })
  })

  const byName = new Map<string, { crossings: RoadCrossing[]; weeks: number[] }>()
  const roadOf = (name: string) => {
    let road = byName.get(name)
    if (!road) byName.set(name, (road = { crossings: [], weeks: [] }))
    return road
  }
  for (const [name, own] of bare) roadOf(name).weeks = addWeeks([], own.weeks)
  for (const crossing of crossings) {
    const [a, b] = crossing.roads
    for (const [name, other] of [
      [a, b],
      [b, a],
    ] as const) {
      const road = roadOf(name)
      road.crossings.push({ id: crossing.id, other, n: crossing.n })
      road.weeks = addWeeks(road.weeks, crossing.weeks)
    }
  }

  const roads = [...byName].map(([name, road]): Road => {
    const crossingsHere = [...road.crossings].sort(
      (x, y) => y.n - x.n || x.other.localeCompare(y.other),
    )
    const own = bare.get(name)?.n ?? 0
    const atCrossings = crossingsHere.reduce((sum, c) => sum + c.n, 0)
    return {
      name,
      own,
      atCrossings,
      total: own + atCrossings,
      weeks: road.weeks,
      crossings: crossingsHere,
      showId: bare.get(name)?.id ?? crossingsHere[0].id,
    }
  })
  roads.sort((a, b) => b.total - a.total || a.name.localeCompare(b.name))
  crossings.sort((a, b) => b.n - a.n || a.name.localeCompare(b.name))
  return { roads, crossings }
}
