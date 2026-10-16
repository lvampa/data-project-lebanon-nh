export const INCIDENT_CATEGORIES = {
  fire: { token: 'chart-1', label: 'Fire' },
  medical: { token: 'chart-2', label: 'Medical' },
  traffic: { token: 'chart-3', label: 'Traffic' },
  utility: { token: 'chart-4', label: 'Utility' },
  police: { token: 'chart-5', label: 'Police' },
} as const

export type CategoryKey = keyof typeof INCIDENT_CATEGORIES
export type CategoryToken = (typeof INCIDENT_CATEGORIES)[CategoryKey]['token']
