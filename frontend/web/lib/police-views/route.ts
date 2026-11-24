// A route number as the log writes it, so "NH Route 120" and "Route 120" are one road, and
// so are "I-89" and "I-89 South".
// This is the same rule as locations/osm.py: the text is upper case, with dots dropped and
// hyphens as spaces, so "I-89" is "I 89".
const ROUTE =
  /^(INTERSTATE|NEW HAMPSHIRE ROUTE|STATE ROUTE|STATE RTE|STATE RT|STATE HWY|US ROUTE|US HIGHWAY|US HWY|NH ROUTE|NH RTE|NH RT|NH HWY|ROUTE|HIGHWAY|RTE|RT|HWY|US|U S|NH|I)\s*(\d{1,3}[A-Z]?)(?:\s+(?:NORTH|SOUTH|EAST|WEST|NORTHBOUND|SOUTHBOUND|EASTBOUND|WESTBOUND|NB|SB|EB|WB))?$/
const BARE = new Set(['ROUTE', 'HIGHWAY', 'RTE', 'RT', 'HWY'])

function parse(name: string): { prefix: string; number: string } | null {
  const cleaned = name.toUpperCase().replaceAll('.', '').replaceAll('-', ' ').split(/\s+/).join(' ')
  const found = ROUTE.exec(cleaned)
  return found ? { prefix: found[1], number: found[2] } : null
}

// The route a name spells out in full, "NH 120" for "NH Route 120", or null for a bare "Route 4",
// which could be a state or a federal road.
export function explicitRouteKey(name: string): string | null {
  const route = parse(name)
  if (!route || BARE.has(route.prefix)) return null
  return routeKey(name)
}

// "I 89", "US 4" or "NH 120" for a road named by its route number, else null. A bare "Route 4"
// takes the federal road when the data names only that one, and the state road otherwise,
// as the snapshot lookup in osm.py lets the data pick. `explicit` is the keys the data names.
export function routeKey(name: string, explicit: ReadonlySet<string> = new Set()): string | null {
  const route = parse(name)
  if (!route) return null
  const { prefix, number } = route
  if (prefix === 'I' || prefix === 'INTERSTATE') return `I ${number}`
  if (prefix.startsWith('US') || prefix.startsWith('U S')) return `US ${number}`
  if (BARE.has(prefix) && explicit.has(`US ${number}`) && !explicit.has(`NH ${number}`)) {
    return `US ${number}`
  }
  return `NH ${number}`
}

// What two spellings of one road share: its route number, or its name in lower case.
export function roadKey(name: string, explicit: ReadonlySet<string> = new Set()): string {
  return routeKey(name, explicit) ?? name.trim().toLowerCase()
}
