import type { ExpressionSpecification } from 'maplibre-gl'

// Road names in the map tiles are spelled out: "N Main St" here is "North Main Street" there.
export const SUFFIX: Record<string, string> = {
  Rd: 'Road',
  St: 'Street',
  Ave: 'Avenue',
  Dr: 'Drive',
  Ln: 'Lane',
  Ct: 'Court',
  Pl: 'Place',
  Blvd: 'Boulevard',
  Pkwy: 'Parkway',
  Hwy: 'Highway',
  Cir: 'Circle',
  Ter: 'Terrace',
  Ext: 'Extension',
}
const DIRECTION: Record<string, string> = { N: 'North', S: 'South', E: 'East', W: 'West' }

// A box around Lebanon, so a street of the same name in another town is not lit.
export const CITY_BOX = {
  type: 'Polygon' as const,
  coordinates: [
    [
      [-72.34, 43.56],
      [-72.17, 43.56],
      [-72.17, 43.69],
      [-72.34, 43.69],
      [-72.34, 43.56],
    ],
  ],
}

// The street or streets of a pin, as the tiles spell them. A place has its street after the
// name, a road is its own street, and an intersection lights both of its streets.
export function osmStreetNames(name: string): string[] {
  const street = (name.includes(', ') ? name.split(', ').slice(1).join(', ') : name)
    .replace(/\s*\(.*?\)\s*/g, '')
    .replace(/^\d+[A-Z]?(-\d+)?\s+/, '')
    .trim()
  return street
    .split(' and ')
    .map((part) =>
      part
        .split(' ')
        .map((word, i) => (i === 0 && DIRECTION[word]) || SUFFIX[word] || word)
        .join(' '),
    )
    .filter((part) => part !== '')
}

export function streetFilter(names: string[]): ExpressionSpecification {
  return ['all', ['in', ['get', 'name'], ['literal', names]], ['within', CITY_BOX]]
}

// Only a road, or a place with traffic on its street, lights the street.
export function streetsToLight(address: {
  kind: 'place' | 'road'
  traffic_count: number
  normalized_address: string | null
  raw_address: string
}): string[] {
  if (address.kind !== 'road' && address.traffic_count === 0) return []
  return osmStreetNames(address.normalized_address ?? address.raw_address)
}
