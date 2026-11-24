import { hiddenCallsByStreet } from '@/lib/police-map/approximate'
import { pinTotal } from '@/lib/police-map/map-style'
import type { Address } from '@/lib/types'
import { roadKey, routeKey } from './route'

export const ROADS_MODES = [
  { id: 'roads', label: 'Roads' },
  { id: 'crossings', label: 'Crossings' },
] as const
export type RoadsMode = (typeof ROADS_MODES)[number]['id']

// One thing that counts at a road's crossings line: a crossing with another road, or a point on
// the road such as an exit.
export interface RoadCrossing {
  // The pin that holds it.
  id: string
  // The other road, or the point, such as "Exit 17".
  other: string
  n: number
}

export interface Road {
  name: string
  // The number on the map for the road: its own pin and the places listed on it, or, with no
  // pin of its own, what its crossings add up to.
  headline: number
  hasOwnPin: boolean
  // What counts at its crossings and points, each also counted on the other road.
  atCrossings: number
  weeks: number[]
  // Busiest first.
  crossings: RoadCrossing[]
  // The pin "Show on the map" opens: the road's own, or its busiest crossing.
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
  /\b(exits?|near|at|between|toward|northbound|southbound|eastbound|westbound|nb|sb|mile marker|(on|off)[- ]?ramp|ramps?|rest area|weigh station|underpass|median|lane|over)\b/i

// "Heater Rd and NH Route 120" is the crossing of those two roads. Anything that is not
// exactly two roads joined by "and" is not a crossing by its name.
export function parseCrossing(name: string): [string, string] | null {
  const parts = name.split(' and ').map((part) => part.trim())
  if (parts.length !== 2 || parts.some((part) => part === '' || DESCRIBES_A_SPOT.test(part))) {
    return null
  }
  return [parts[0], parts[1]]
}

const EXIT_PHRASE = /\bexits?\s+\d+[a-z]?(?:\s*(?:and|to|-)\s*\d+[a-z]?)?/gi
const NOT_A_ROAD =
  /\b(northbound|southbound|eastbound|westbound|nb|sb|(on|off)[- ]?ramp|ramps?|rest area|weigh station|underpass|median|lane|interchange|mile marker [\d.]+)\b/gi
const BETWEEN_PARTS =
  /\b(?:near|at|between|over|under|toward|before|after|from|with|onto|and)\b|[,()]/i

// What a pin named for a spot describes: the roads it names, and the point it gives. "I-89 near
// Mechanic St" names two roads. "I-89 northbound near Exit 17" names one road and a point.
// `isRoad` tells a road from a landmark, such as a store. A name that names no road is null.
export function parseSpot(
  name: string,
  isRoad: (text: string) => boolean,
): { roads: string[]; point: string | null } | null {
  const exit = name.match(EXIT_PHRASE)?.[0] ?? null
  const parts = name
    .replace(EXIT_PHRASE, ',')
    .replace(NOT_A_ROAD, ' ')
    .split(BETWEEN_PARTS)
    .map((part) => part.split(/\s+/).filter(Boolean).join(' '))
    .filter((part) => part !== '')
  const roads: string[] = []
  for (const part of parts) {
    if (isRoad(part) && !roads.some((road) => roadKey(road) === roadKey(part))) roads.push(part)
  }
  if (roads.length === 0) return null
  return { roads, point: exit ? exit.replace(/^exits?/i, 'Exit') : null }
}

function addWeeks(into: number[], weeks: number[]): number[] {
  const sum = [...into, ...new Array(Math.max(0, weeks.length - into.length)).fill(0)]
  weeks.forEach((value, week) => (sum[week] += value))
  return sum
}

interface Acc {
  name: string
  own: { id: string; n: number; weeks: number[] } | null
  items: (RoadCrossing & { weeks: number[] })[]
}

// A road's number is the map's number for it. What happens where it meets another road is
// counted on its own line, and a crossing counts on both of its roads. `addresses` carry the
// counts the filters keep, as the map's do, and `weeks` has each pin's entries by week, keyed
// by index into `addresses`. A pin with nothing to show is left out, as on the map.
export function buildRoads(
  addresses: Address[],
  weeks: Map<number, number[]>,
): { roads: Road[]; crossings: Crossing[] } {
  const listedOn = hiddenCallsByStreet(addresses)
  const pins = addresses.flatMap((address, index) => {
    const n = pinTotal(address, listedOn)
    if (address.kind !== 'road' || address.hidden || n === 0) return []
    return [
      {
        id: address.id,
        name: address.normalized_address ?? address.raw_address,
        n,
        weeks: weeks.get(index) ?? [],
      },
    ]
  })

  // Pass one: the roads the plain names give, so a spot description can tell a road from a store.
  const roads = new Map<string, Acc>()
  const roadFor = (name: string): Acc => {
    let road = roads.get(roadKey(name))
    if (!road) roads.set(roadKey(name), (road = { name, own: null, items: [] }))
    return road
  }
  const spots: typeof pins = []
  for (const pin of pins) {
    if (DESCRIBES_A_SPOT.test(pin.name)) {
      spots.push(pin)
      continue
    }
    const legs = parseCrossing(pin.name)
    if (legs) {
      legs.forEach(roadFor)
      continue
    }
    const road = roadFor(pin.name)
    road.name = pin.name
    // Two pins with one name are one road, shown on the busier. The map still draws both.
    const known = road.own
    road.own = {
      id: known && known.n >= pin.n ? known.id : pin.id,
      n: (known?.n ?? 0) + pin.n,
      weeks: addWeeks(known?.weeks ?? [], pin.weeks),
    }
  }

  const crossings = new Map<string, Crossing>()
  const cross = (pin: (typeof pins)[number], a: string, b: string) => {
    const [first, second] = [roadFor(a).name, roadFor(b).name].sort((x, y) => x.localeCompare(y))
    const key = `${roadKey(first)}|${roadKey(second)}`
    const known = crossings.get(key)
    if (known) {
      known.id = known.n >= pin.n ? known.id : pin.id
      known.n += pin.n
      known.weeks = addWeeks(known.weeks, pin.weeks)
    } else {
      crossings.set(key, {
        id: pin.id,
        name: `${first} and ${second}`,
        roads: [first, second],
        n: pin.n,
        weeks: [...pin.weeks],
      })
    }
    for (const [road, other] of [
      [first, second],
      [second, first],
    ]) {
      roadFor(road).items.push({ id: pin.id, other, n: pin.n, weeks: pin.weeks })
    }
  }
  for (const pin of pins) {
    if (DESCRIBES_A_SPOT.test(pin.name)) continue
    const legs = parseCrossing(pin.name)
    if (legs) cross(pin, legs[0], legs[1])
  }
  for (const pin of spots) {
    const spot = parseSpot(pin.name, (text) => roads.has(roadKey(text)) || routeKey(text) !== null)
    if (!spot) {
      // No road in it: it is a road of its own, as it was named.
      const road = roadFor(pin.name)
      road.own = {
        id: pin.id,
        n: (road.own?.n ?? 0) + pin.n,
        weeks: addWeeks(road.own?.weeks ?? [], pin.weeks),
      }
    } else if (spot.roads.length >= 2) {
      cross(pin, spot.roads[0], spot.roads[1])
    } else {
      roadFor(spot.roads[0]).items.push({
        id: pin.id,
        other: spot.point ?? 'a point on it',
        n: pin.n,
        weeks: pin.weeks,
      })
    }
  }

  const result = [...roads.values()].map((road): Road => {
    const items = mergeItems(road.items)
    const atCrossings = items.reduce((sum, item) => sum + item.n, 0)
    const own = road.own
    return {
      name: road.name,
      headline: own ? own.n : atCrossings,
      hasOwnPin: own !== null,
      atCrossings,
      weeks: own
        ? own.weeks
        : items.reduce((sum, item) => addWeeks(sum, item.weeks), [] as number[]),
      crossings: items.map(({ id, other, n }) => ({ id, other, n })),
      showId: own?.id ?? items[0].id,
    }
  })
  result.sort((a, b) => b.headline - a.headline || a.name.localeCompare(b.name))
  const crossingList = [...crossings.values()].sort(
    (a, b) => b.n - a.n || a.name.localeCompare(b.name),
  )
  return { roads: result, crossings: crossingList }
}

// One row for each other road or point, busiest first. Spellings of one crossing on a road add up.
function mergeItems(items: (RoadCrossing & { weeks: number[] })[]) {
  const byOther = new Map<string, RoadCrossing & { weeks: number[] }>()
  for (const item of items) {
    const known = byOther.get(item.other)
    if (known) {
      known.id = known.n >= item.n ? known.id : item.id
      known.n += item.n
      known.weeks = addWeeks(known.weeks, item.weeks)
    } else {
      byOther.set(item.other, { ...item, weeks: [...item.weeks] })
    }
  }
  return [...byOther.values()].sort((a, b) => b.n - a.n || a.other.localeCompare(b.other))
}
