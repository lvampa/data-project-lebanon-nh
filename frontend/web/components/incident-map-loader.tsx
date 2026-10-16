'use client'
import dynamic from 'next/dynamic'
import type { Address } from '@/lib/types'

const IncidentMap = dynamic(() => import('@/components/incident-map').then((m) => m.IncidentMap), {
  ssr: false,
  loading: () => (
    <div
      className="w-full rounded-lg border flex items-center justify-center text-muted-foreground text-sm"
      style={{ height: '600px' }}
    >
      Loading map…
    </div>
  ),
})

interface Props {
  addresses: Address[]
}

export function IncidentMapLoader({ addresses }: Props) {
  return <IncidentMap addresses={addresses} />
}
