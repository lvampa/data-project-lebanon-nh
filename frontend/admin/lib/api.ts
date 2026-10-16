import type {
  IncidentsResponse,
  TypeStat,
  HourStat,
  WeekdayStat,
  AddressRecord,
  CategoryRecord,
  LlcsResponse,
  SearchResponse,
} from './types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function apiFetch<T>(url: URL | string): Promise<T> {
  const res = await fetch(url, { cache: 'no-store' })
  if (!res.ok) throw new Error(`API error ${res.status} — ${url}`)
  return res.json() as Promise<T>
}

export async function fetchIncidents(params: {
  date_from?: string
  date_to?: string
  incident_type?: string
  officer?: string
  page?: number
  per_page?: number
}): Promise<IncidentsResponse> {
  const url = new URL(`${API_BASE}/api/incidents`)
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') url.searchParams.set(k, String(v))
  }
  return apiFetch(url)
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

export async function fetchAddresses(): Promise<AddressRecord[]> {
  return apiFetch(`${API_BASE}/api/addresses`)
}

export async function fetchCategories(): Promise<CategoryRecord[]> {
  return apiFetch(`${API_BASE}/api/categories`)
}

export async function fetchLlcs(params?: { lookup_status?: string }): Promise<LlcsResponse> {
  const url = new URL(`${API_BASE}/api/llcs`)
  if (params?.lookup_status) url.searchParams.set('lookup_status', params.lookup_status)
  return apiFetch(url)
}

export async function updateLlcStatus(id: number, status: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/llcs/${id}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lookup_status: status }),
  })
  if (!res.ok) throw new Error(`Failed to update LLC ${id} status: ${res.status}`)
}

export async function fetchSearch(q: string): Promise<SearchResponse> {
  const url = new URL(`${API_BASE}/api/search`)
  url.searchParams.set('q', q)
  return apiFetch<SearchResponse>(url)
}
