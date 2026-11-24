// Where the exported JSON lives. Local dev and the built site serve it from /data; a separate
// data host is set with NEXT_PUBLIC_DATA_URL when the build is deployed without data.
// An empty value, as an unset CI variable gives, counts as unset.
const DATA_URL = (process.env.NEXT_PUBLIC_DATA_URL || '/data').replace(/\/+$/, '')

// Every file the site fetches, so a name is spelled once.
export const DATA_FILES = {
  activity: 'activity.json',
  addresses: 'addresses.json',
  incidents: 'incidents.json',
  properties: 'properties.json',
  staff: 'staff.json',
  stats: 'stats.json',
} as const

export function placeFile(id: string): string {
  return `places/${encodeURIComponent(id)}.json`
}

export function dataUrl(filename: string): string {
  return `${DATA_URL}/${filename}`
}

export async function fetchDataFile<T>(filename: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(dataUrl(filename), { signal })
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  return (await response.json()) as T
}
