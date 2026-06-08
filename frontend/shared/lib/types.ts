/** Types shared between web and admin packages. */

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
