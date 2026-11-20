import type { TypeStat, WeekdayStat } from '@project/ui/lib/types'

export type { Incident, TypeStat, WeekdayStat } from '@project/ui/lib/types'

export interface HourStat {
  hour: number
  count: number
}

export interface StatsData {
  total: number
  generated_at: string
  since: string
  by_type: TypeStat[]
  by_weekday: WeekdayStat[]
  by_hour: HourStat[]
}

export interface Address {
  // A slug of the normalized address. It names the place's card, data/places/<id>.json.
  id: string
  // A road is a bare street, an intersection or a highway.
  kind: 'place' | 'road'
  raw_address: string
  normalized_address: string | null
  count: number
  traffic_count: number
  lat: number
  lng: number
  // 'approximate' when the point is only somewhere on the place's street.
  precision: 'exact' | 'approximate'
  // The street pin an approximate place is listed on, when it has one.
  street_id: string | null
  // True when the place has no pin of its own. It stays in the list so counts and ranks
  // are unchanged, and the map leaves it out.
  hidden: boolean
}

// One call on a place's card.
export interface PlaceCall {
  reported_at: string | null
  incident_type: string | null
  disposition: string | null
  call_source: string | null
  category: string
  source_url: string
  case_number: string
  dispatched_at: string | null
  arrived_at: string | null
  cleared_at: string | null
  officer: string | null
}

// data/places/<id>.json: the report card for one pin.
export interface PlaceCard {
  name: string
  kind: 'place' | 'road'
  lat: number
  lng: number
  count: number
  categories: Record<'premises' | 'traffic' | 'alarms' | 'checks' | 'admin', number>
  // [incident type, calls]. A road lists every type, and a place only what happened there.
  types: [string, number][]
  // [disposition, calls], for the calls at the place itself.
  outcomes: [string, number][]
  calls: PlaceCall[]
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
