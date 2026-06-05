'use client'
import { useMemo, useState } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams, usePathname } from 'next/navigation'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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
          defaultValue={q}
          className="max-w-sm"
          onBlur={e => updateQ(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter') updateQ((e.target as HTMLInputElement).value)
          }}
        />
        {q && (
          <Button variant="ghost" onClick={() => router.replace(pathname)}>
            Clear
          </Button>
        )}
      </div>
      <p className="text-sm text-muted-foreground mb-2">
        {filtered.length.toLocaleString()} properties
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Address</TableHead>
            <TableHead>Owner</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Assessed</TableHead>
            <TableHead>Built</TableHead>
            <TableHead>Sqft</TableHead>
            <TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {slice.map(p => (
            <TableRow key={p.parcel_id}>
              <TableCell className="font-medium text-sm">
                {p.location ?? '—'}
              </TableCell>
              <TableCell className="text-sm">{p.owner ?? '—'}</TableCell>
              <TableCell className="text-xs">
                {p.land_use && (
                  <Badge variant="outline" className="text-xs">
                    {p.land_use}
                  </Badge>
                )}
              </TableCell>
              <TableCell className="text-sm tabular-nums">
                {p.assessed_total != null
                  ? `$${p.assessed_total.toLocaleString()}`
                  : '—'}
              </TableCell>
              <TableCell className="text-sm">{p.year_built ?? '—'}</TableCell>
              <TableCell className="text-sm tabular-nums">
                {p.building_sqft != null
                  ? p.building_sqft.toLocaleString()
                  : '—'}
              </TableCell>
              <TableCell>
                {p.detail_url && (
                  <Link
                    href={p.detail_url}
                    target="_blank"
                    className="text-xs text-blue-600 hover:underline"
                  >
                    VGSI →
                  </Link>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {totalPages > 1 && (
        <div className="flex items-center gap-2 mt-4">
          {page > 1 && (
            <Button variant="outline" size="sm" onClick={() => setPage(p => p - 1)}>
              ← Prev
            </Button>
          )}
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          {page < totalPages && (
            <Button variant="outline" size="sm" onClick={() => setPage(p => p + 1)}>
              Next →
            </Button>
          )}
        </div>
      )}
    </div>
  )
}
