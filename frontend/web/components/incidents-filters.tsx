'use client'
import { useRouter, useSearchParams, usePathname } from 'next/navigation'
import { useCallback } from 'react'
import { Input } from '@project/ui/components/ui/input'
import { Button } from '@project/ui/components/ui/button'

export function IncidentsFilters() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  const updateFilter = useCallback(
    (key: string, value: string) => {
      const params = new URLSearchParams(searchParams.toString())
      if (value) {
        params.set(key, value)
      } else {
        params.delete(key)
      }
      router.replace(`${pathname}?${params.toString()}`)
    },
    [router, pathname, searchParams],
  )

  const hasFilters = searchParams.has('incident_type') || searchParams.has('officer')

  return (
    <div className="flex gap-2 mb-4 flex-wrap">
      <Input
        placeholder="Incident type…"
        defaultValue={searchParams.get('incident_type') ?? ''}
        className="w-48"
        onBlur={(e) => updateFilter('incident_type', e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') updateFilter('incident_type', (e.target as HTMLInputElement).value)
        }}
      />
      <Input
        placeholder="Officer…"
        defaultValue={searchParams.get('officer') ?? ''}
        className="w-36"
        onBlur={(e) => updateFilter('officer', e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') updateFilter('officer', (e.target as HTMLInputElement).value)
        }}
      />
      {hasFilters && (
        <Button variant="ghost" onClick={() => router.replace(pathname)}>
          Clear
        </Button>
      )}
    </div>
  )
}
