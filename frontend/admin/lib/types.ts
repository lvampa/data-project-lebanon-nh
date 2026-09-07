import type { Incident } from '@project/ui/lib/types'

export type { Incident, TypeStat, WeekdayStat } from '@project/ui/lib/types'

export interface IncidentsResponse {
  total: number
  page: number
  per_page: number
  items: Incident[]
}

export interface HourStat {
  hour: number
  count: number
}

export interface AddressRecord {
  raw_address: string
  count: number
  normalized_address: string | null
  lat: number | null
  lng: number | null
  is_normalized: boolean
}

export interface CategoryRecord {
  raw_incident_type: string
  count: number
  category: string | null
  subcategory: string | null
  is_categorized: boolean
}

export interface LlcPrincipal {
  name: string
  title: string
  address?: string | null
}

export interface Llc {
  id: number
  name: string
  raw_owner_name: string | null
  lookup_status: string
  nh_business_id: string | null
  business_status: string | null
  formation_date: string | null
  business_email: string | null
  phone: string | null
  registered_agent: string | null
  registered_agent_address: string | null
  principals: LlcPrincipal[] | null
  last_looked_up_at: string | null
  error_message: string | null
}

export interface LlcsResponse {
  total: number
  items: Llc[]
}

export interface SearchResult {
  id: number
  entity_type: string
  score: number
  data: Record<string, unknown>
}

export interface SearchResponse {
  query: string
  normalized_query: string | null
  results: Record<string, SearchResult[]>
}
