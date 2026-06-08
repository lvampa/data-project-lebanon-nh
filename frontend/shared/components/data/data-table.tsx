'use client'
import React, { useState, useMemo } from 'react'
import { cn } from '../../lib/utils'

type SortDir = 'asc' | 'desc' | null

export interface DataTableColumn<T> {
  id: string
  header: string
  numeric?: boolean
  align?: 'left' | 'right' | 'center'
  width?: number | string
  sortable?: boolean
  /** Custom sort value extractor */
  sortBy?: (row: T) => unknown
  /** Custom cell renderer */
  accessor?: (row: T) => React.ReactNode
}

interface DataTableProps<T> {
  columns: DataTableColumn<T>[]
  rows: T[]
  rowKey?: (row: T, index: number) => React.Key
  density?: 'compact' | 'comfortable'
  bordered?: boolean
  stickyHeader?: boolean
  hoverable?: boolean
  caption?: React.ReactNode
  empty?: React.ReactNode
  onRowClick?: (row: T) => void
  className?: string
}

export function DataTable<T extends Record<string, unknown>>({
  columns,
  rows,
  rowKey = (_, i) => i,
  density = 'comfortable',
  bordered = true,
  stickyHeader = false,
  hoverable = true,
  caption,
  empty = 'No data.',
  onRowClick,
  className,
}: DataTableProps<T>) {
  const [sort, setSort] = useState<{ id: string; dir: 'asc' | 'desc' } | null>(null)

  const sorted = useMemo(() => {
    if (!sort) return rows
    const col = columns.find((c) => c.id === sort.id)
    if (!col) return rows
    const get = col.sortBy ?? ((r: T) => r[col.id])
    const out = [...rows].sort((a, b) => {
      const va = get(a)
      const vb = get(b)
      if (va == null) return 1
      if (vb == null) return -1
      if (typeof va === 'number' && typeof vb === 'number') return va - vb
      return String(va).localeCompare(String(vb))
    })
    if (sort.dir === 'desc') out.reverse()
    return out
  }, [rows, columns, sort])

  const handleHeaderClick = (col: DataTableColumn<T>) => {
    if (!col.sortable) return
    setSort((prev) => {
      if (!prev || prev.id !== col.id) return { id: col.id, dir: 'asc' }
      if (prev.dir === 'asc') return { id: col.id, dir: 'desc' }
      return null
    })
  }

  const cellPy = density === 'compact' ? 'py-1.5' : 'py-2.5'
  const headPy = density === 'compact' ? 'py-2' : 'py-2.5'

  return (
    <div
      className={cn(
        'w-full overflow-auto',
        bordered && 'rounded-lg border border-border',
        className,
      )}
    >
      <table className="w-full border-collapse text-[13px] text-foreground">
        <thead>
          <tr className="border-b border-border bg-muted">
            {columns.map((col) => {
              const isActive = sort?.id === col.id
              const isNumeric = col.numeric || col.align === 'right'
              return (
                <th
                  key={col.id}
                  style={{ width: col.width, textAlign: col.align }}
                  className={cn(
                    'px-3 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground whitespace-nowrap',
                    headPy,
                    !col.align && (isNumeric ? 'text-right' : 'text-left'),
                    col.sortable && 'cursor-pointer select-none hover:text-foreground',
                    stickyHeader && 'sticky top-0 z-10 bg-muted',
                  )}
                  data-sort={isActive ? sort?.dir : undefined}
                  onClick={() => handleHeaderClick(col)}
                >
                  <span className="inline-flex items-center gap-1">
                    <span>{col.header}</span>
                    {col.sortable && (
                      <span className={cn('text-[9px]', isActive ? 'text-foreground' : 'text-muted-foreground/50')}>
                        {isActive ? (sort?.dir === 'asc' ? '▲' : '▼') : '▴▾'}
                      </span>
                    )}
                  </span>
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="px-3 py-6 text-center text-sm text-muted-foreground"
              >
                {empty}
              </td>
            </tr>
          ) : (
            sorted.map((row, i) => (
              <tr
                key={rowKey(row, i)}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={cn(
                  'border-b border-border/60 last:border-b-0 transition-colors',
                  hoverable && 'hover:bg-muted/30',
                  onRowClick && 'cursor-pointer',
                )}
              >
                {columns.map((col) => {
                  const isNumeric = col.numeric || col.align === 'right'
                  return (
                    <td
                      key={col.id}
                      style={{ textAlign: col.align }}
                      className={cn(
                        'px-3',
                        cellPy,
                        !col.align && (isNumeric ? 'text-right font-mono tabular-nums' : ''),
                      )}
                    >
                      {col.accessor
                        ? col.accessor(row)
                        : row[col.id] != null
                          ? (row[col.id] as React.ReactNode)
                          : <span className="text-muted-foreground">—</span>}
                    </td>
                  )
                })}
              </tr>
            ))
          )}
        </tbody>
      </table>
      {caption && (
        <div className="border-t border-border bg-muted px-3 py-2.5 text-[11px] text-muted-foreground">
          {caption}
        </div>
      )}
    </div>
  )
}
