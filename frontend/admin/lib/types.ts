export interface Incident {
  case_number: string | null
  reported_at: string | null
  call_source: string | null
  incident_type: string | null
  disposition: string | null
  location: string | null
  officer: string | null
  reference_number: string | null
  source_url: string
}

export interface IncidentsResponse {
  total: number
  page: number
  per_page: number
  items: Incident[]
}

export interface TypeStat {
  incident_type: string
  count: number
}

export interface HourStat {
  hour: number
  count: number
}

export interface WeekdayStat {
  day: string
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
