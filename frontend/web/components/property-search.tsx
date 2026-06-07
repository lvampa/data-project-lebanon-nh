'use client'
import { useMemo, useState, useEffect } from 'react'
import { useRouter, useSearchParams, usePathname } from 'next/navigation'
import { Button } from '@project/ui/components/ui/button'
import { Input } from '@project/ui/components/ui/input'
import { Pagination } from '@/components/pagination'
import { PropertyTable } from '@/components/property-table'
import type { PropertyRecord } from '@/lib/types'

const PER_PAGE = 50

interface Props {
  properties: PropertyRecord[]
}

export function PropertySearch({ properties }: Props) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const [page, setPage] = useState(1)

  const q = searchParams.get('q') ?? ''

  useEffect(() => {
    setPage(1)
  }, [q])

  const filtered = useMemo(() => {
    if (!q) return properties
    const lower = q.toLowerCase()
    return properties.filter(
      p =>
        (p.location ?? '').toLowerCase().includes(lower) ||
        (p.owner ?? '').toLowerCase().includes(lower),
    )
  }, [properties, q])

  const totalPages = Math.max(1, Math.ceil(filtered.length / PER_PAGE))
  const slice = filtered.slice((page - 1) * PER_PAGE, page * PER_PAGE)

  const updateQ = (value: string) => {
    const params = new URLSearchParams(searchParams.toString())
    if (value) params.set('q', value)
    else params.delete('q')
    router.replace(`${pathname}?${params.toString()}`)
    setPage(1)
  }

  return (
    <div>
      <div className="flex gap-2 mb-4">
        <Input
          placeholder="Search by address or owner…"
          value={q}
          className="max-w-sm"
          onChange={e => updateQ(e.target.value)}
        />
        {q && (
          <Button variant="ghost" onClick={() => { router.replace(pathname); setPage(1) }}>
            Clear
          </Button>
        )}
      </div>
      <p className="text-sm text-muted-foreground mb-2">
        {filtered.length.toLocaleString()} properties
      </p>
      <PropertyTable properties={slice} />
      <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />
    </div>
  )
}
