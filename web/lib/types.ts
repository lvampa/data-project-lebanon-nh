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

export interface TypeStat {
  incident_type: string
  count: number
}

export interface WeekdayStat {
  day: string
  count: number
}

export interface StatsData {
  total: number
  generated_at: string
  by_type: TypeStat[]
  by_weekday: WeekdayStat[]
}

export interface Address {
  raw_address: string
  normalized_address: string | null
  count: number
  lat: number
  lng: number
}

export interface StaffMember {
  id: number
  name: string
  title: string | null
  department: string
  division: string | null
  email: string | null
  phone: string | null
  source_url: string
}
