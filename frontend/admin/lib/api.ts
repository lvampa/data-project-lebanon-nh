import type {
  Incident,
  Page,
  TypeStat,
  HourStat,
  WeekdayStat,
  AddressRecord,
  CategoryRecord,
  Llc,
  SearchResponse,
} from './types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

type Paging = { page?: number; per_page?: number }

function apiUrl(path: string, params: Record<string, string | number | undefined> = {}): URL {
  const url = new URL(`${API_BASE}${path}`)
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') url.searchParams.set(k, String(v))
  }
  return url
}

async function apiFetch<T>(url: URL | string): Promise<T> {
  const res = await fetch(url, { cache: 'no-store' })
  if (!res.ok) throw new Error(`API error ${res.status} — ${url}`)
  return res.json() as Promise<T>
}

export async function fetchIncidents(
  params: {
    date_from?: string
    date_to?: string
    incident_type?: string
    officer?: string
  } & Paging,
): Promise<Page<Incident>> {
  return apiFetch(apiUrl('/api/incidents', params))
}

export async function fetchStatsByType(): Promise<TypeStat[]> {
  return apiFetch(`${API_BASE}/api/stats/by-type`)
}

export async function fetchStatsByHour(): Promise<HourStat[]> {
  return apiFetch(`${API_BASE}/api/stats/by-hour`)
}

export async function fetchStatsByWeekday(): Promise<WeekdayStat[]> {
  return apiFetch(`${API_BASE}/api/stats/by-weekday`)
}

export async function fetchAddresses(params: Paging = {}): Promise<Page<AddressRecord>> {
  return apiFetch(apiUrl('/api/addresses', params))
}

export async function fetchCategories(params: Paging = {}): Promise<Page<CategoryRecord>> {
  return apiFetch(apiUrl('/api/categories', params))
}

export async function fetchLlcs(
  params: { lookup_status?: string } & Paging = {},
): Promise<Page<Llc>> {
  return apiFetch(apiUrl('/api/llcs', params))
}

export async function updateLlcStatus(id: number, status: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/llcs/${id}/status`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      // Server-only on purpose: Next.js never ships a non-NEXT_PUBLIC_ var to the browser.
      Authorization: `Bearer ${process.env.ADMIN_API_TOKEN}`,
    },
    body: JSON.stringify({ lookup_status: status }),
  })
  if (!res.ok) throw new Error(`Failed to update LLC ${id} status: ${res.status}`)
}

export async function fetchSearch(q: string): Promise<SearchResponse> {
  const url = new URL(`${API_BASE}/api/search`)
  url.searchParams.set('q', q)
  return apiFetch<SearchResponse>(url)
}
