// A route number as the log writes it, so "NH Route 120" and "Route 120" are one road.
// This is the same rule as locations/osm.py: the text is upper case, with dots dropped and
// hyphens as spaces, so "I-89" is "I 89".
const ROUTE =
  /^(INTERSTATE|NEW HAMPSHIRE ROUTE|STATE ROUTE|STATE RTE|STATE RT|STATE HWY|US ROUTE|US HIGHWAY|US HWY|NH ROUTE|NH RTE|NH RT|NH HWY|ROUTE|HIGHWAY|RTE|RT|HWY|US|U S|NH|I)\s*(\d{1,3}[A-Z]?)$/

// "I 89", "US 4" or "NH 120" for a road named by its route number, else null. A bare "Route"
// is a state route here, since the only bare route the log names in Lebanon is NH 120.
export function routeKey(name: string): string | null {
  const cleaned = name.toUpperCase().replaceAll('.', '').replaceAll('-', ' ').split(/\s+/).join(' ')
  const found = ROUTE.exec(cleaned)
  if (!found) return null
  const [, prefix, number] = found
  if (prefix === 'I' || prefix === 'INTERSTATE') return `I ${number}`
  if (prefix.startsWith('US') || prefix.startsWith('U S')) return `US ${number}`
  return `NH ${number}`
}

// What two spellings of one road share: its route number, or its name in lower case.
export function roadKey(name: string): string {
  return routeKey(name) ?? name.trim().toLowerCase()
}
