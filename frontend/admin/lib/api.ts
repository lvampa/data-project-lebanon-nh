import type {
  IncidentsResponse,
  TypeStat,
  HourStat,
  WeekdayStat,
  AddressRecord,
  CategoryRecord,
  LlcsResponse,
} from './types'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

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
  const res = await fetch(url, { cache: 'no-store' })
  return res.json()
}

export async function fetchStatsByType(): Promise<TypeStat[]> {
  const res = await fetch(`${API_BASE}/api/stats/by-type`, { cache: 'no-store' })
  return res.json()
}

export async function fetchStatsByHour(): Promise<HourStat[]> {
  const res = await fetch(`${API_BASE}/api/stats/by-hour`, { cache: 'no-store' })
  return res.json()
}

export async function fetchStatsByWeekday(): Promise<WeekdayStat[]> {
  const res = await fetch(`${API_BASE}/api/stats/by-weekday`, { cache: 'no-store' })
  return res.json()
}

export async function fetchAddresses(): Promise<AddressRecord[]> {
  const res = await fetch(`${API_BASE}/api/addresses`, { cache: 'no-store' })
  return res.json()
}

export async function fetchCategories(): Promise<CategoryRecord[]> {
  const res = await fetch(`${API_BASE}/api/categories`, { cache: 'no-store' })
  return res.json()
}

export async function fetchLlcs(params?: {
  lookup_status?: string
}): Promise<LlcsResponse> {
  const url = new URL(`${API_BASE}/api/llcs`)
  if (params?.lookup_status) url.searchParams.set('lookup_status', params.lookup_status)
  const res = await fetch(url, { cache: 'no-store' })
  return res.json()
}

export async function updateLlcStatus(id: number, status: string): Promise<void> {
  await fetch(`${API_BASE}/api/llcs/${id}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ lookup_status: status }),
  })
}
