'use client'
import React, { useState, useMemo } from 'react'
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react'
import { cn } from '../../lib/utils'

type SortDir = 'asc' | 'desc' | null

export interface DataTableColumn<T> {
  key: keyof T | string
  header: string
  numeric?: boolean
  sortable?: boolean
  render?: (row: T) => React.ReactNode
}

interface DataTableProps<T> {
  columns: DataTableColumn<T>[]
  data: T[]
  density?: 'compact' | 'comfortable'
  bordered?: boolean
  onRowClick?: (row: T) => void
  emptyMessage?: string
  className?: string
}

export function DataTable<T extends Record<string, unknown>>({
  columns,
  data,
  density = 'comfortable',
  bordered = false,
  onRowClick,
  emptyMessage = 'No data',
  className,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<SortDir>(null)

  const handleSort = (key: string) => {
    if (sortKey !== key) {
      setSortKey(key)
      setSortDir('asc')
    } else if (sortDir === 'asc') {
      setSortDir('desc')
    } else if (sortDir === 'desc') {
      setSortKey(null)
      setSortDir(null)
    }
  }

  const sorted = useMemo(() => {
    if (!sortKey || !sortDir) return data
    return [...data].sort((a, b) => {
      const av = a[sortKey]
      const bv = b[sortKey]
      if (av == null && bv == null) return 0
      if (av == null) return 1
      if (bv == null) return -1
      const cmp = av < bv ? -1 : av > bv ? 1 : 0
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [data, sortKey, sortDir])

  const py = density === 'compact' ? 'py-1.5' : 'py-2.5'

  return (
    <div className={cn('w-full overflow-auto', className)}>
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-border">
            {columns.map((col) => (
              <th
                key={String(col.key)}
                className={cn(
                  'px-3 text-[11px] font-medium uppercase tracking-wide text-muted-foreground',
                  py,
                  col.numeric ? 'text-right' : 'text-left',
                  col.sortable && 'cursor-pointer select-none hover:text-foreground',
                  bordered && 'border-r border-border last:border-r-0',
                )}
                onClick={col.sortable ? () => handleSort(String(col.key)) : undefined}
              >
                <span className="inline-flex items-center gap-1">
                  {col.header}
                  {col.sortable && (
                    <SortIcon sortKey={String(col.key)} activeKey={sortKey} dir={sortDir} />
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="px-3 py-8 text-center text-sm text-muted-foreground"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            sorted.map((row, i) => (
              <tr
                key={i}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={cn(
                  'border-b border-border last:border-b-0 transition-colors',
                  onRowClick && 'cursor-pointer hover:bg-muted/50',
                )}
              >
                {columns.map((col) => (
                  <td
                    key={String(col.key)}
                    className={cn(
                      'px-3 text-[13px] text-foreground',
                      py,
                      col.numeric && 'text-right font-mono tabular-nums',
                      bordered && 'border-r border-border last:border-r-0',
                    )}
                  >
                    {col.render
                      ? col.render(row)
                      : (row[String(col.key)] as React.ReactNode) ?? (
                          <span className="text-muted-foreground">—</span>
                        )}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}

function SortIcon({
  sortKey,
  activeKey,
  dir,
}: {
  sortKey: string
  activeKey: string | null
  dir: SortDir
}) {
  if (activeKey !== sortKey) return <ChevronsUpDown size={12} className="opacity-40" />
  if (dir === 'asc') return <ChevronUp size={12} />
  if (dir === 'desc') return <ChevronDown size={12} />
  return <ChevronsUpDown size={12} className="opacity-40" />
}
