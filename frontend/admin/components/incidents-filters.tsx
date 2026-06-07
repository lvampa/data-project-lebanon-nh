'use client'

import { useRouter, useSearchParams } from 'next/navigation'
import { Input } from '@project/ui/components/ui/input'
import { Button } from '@project/ui/components/ui/button'

export function IncidentsFilters() {
  const router = useRouter()
  const searchParams = useSearchParams()

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    const params = new URLSearchParams()
    for (const [k, v] of form.entries()) {
      if (v) params.set(k, String(v))
    }
    router.push(`/incidents?${params}`)
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap gap-2 mb-4">
      <Input
        name="date_from"
        type="date"
        defaultValue={searchParams.get('date_from') ?? ''}
        className="w-36"
      />
      <Input
        name="date_to"
        type="date"
        defaultValue={searchParams.get('date_to') ?? ''}
        className="w-36"
      />
      <Input
        name="incident_type"
        placeholder="Incident type"
        defaultValue={searchParams.get('incident_type') ?? ''}
        className="w-44"
      />
      <Input
        name="officer"
        placeholder="Officer"
        defaultValue={searchParams.get('officer') ?? ''}
        className="w-36"
      />
      <Button type="submit">Search</Button>
    </form>
  )
}
