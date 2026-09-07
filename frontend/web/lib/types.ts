import type { TypeStat, WeekdayStat } from '@project/ui/lib/types'

export type { Incident, TypeStat, WeekdayStat } from '@project/ui/lib/types'

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

export interface PropertyRecord {
  parcel_id: string
  location: string | null
  owner: string | null
  owner_address: string | null
  land_use: string | null
  lot_size_acres: number | null
  year_built: number | null
  building_sqft: number | null
  assessed_land: number | null
  assessed_building: number | null
  assessed_total: number | null
  assessment_year: number | null
  detail_url: string | null
}
