import React from 'react'

export interface LegendCategory {
  label: string
  count: number | string
  colorVar: string
}

const DEFAULT_CATEGORIES: LegendCategory[] = [
  { label: 'Fire', count: 38, colorVar: '--chart-1' },
  { label: 'Medical', count: 214, colorVar: '--chart-2' },
  { label: 'Traffic', count: 96, colorVar: '--chart-3' },
  { label: 'Utility', count: 12, colorVar: '--chart-4' },
  { label: 'Police', count: 151, colorVar: '--chart-5' },
]

interface MapLegendProps {
  categories?: LegendCategory[]
  total?: number
  variant?: 'stacked' | 'inline'
  status?: string
  lastUpdated?: string
}

export function MapLegend({
  categories = DEFAULT_CATEGORIES,
  total,
  variant = 'stacked',
  status = 'Verified',
  lastUpdated,
}: MapLegendProps) {
  const halo = '0 1px 2px rgba(0,0,0,0.06), 0 0 0 4px var(--background)'

  if (variant === 'inline') {
    return (
      <div
        style={{
          background: 'var(--card)',
          color: 'var(--card-foreground)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius)',
          padding: '6px 10px',
          boxShadow: halo,
          display: 'inline-flex',
          alignItems: 'center',
          gap: 14,
          fontSize: 11,
        }}
      >
        <span
          style={{
            fontSize: 10,
            color: 'var(--muted-foreground)',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            whiteSpace: 'nowrap',
          }}
        >
          Categories
        </span>
        {categories.map((cat) => (
          <span
            key={cat.label}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 5, whiteSpace: 'nowrap' }}
          >
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: 999,
                background: `var(${cat.colorVar})`,
                boxShadow: '0 0 0 1.5px var(--background)',
                flexShrink: 0,
              }}
            />
            <span>{cat.label}</span>
            <span style={{ color: 'var(--muted-foreground)', fontVariantNumeric: 'tabular-nums' }}>
              {cat.count}
            </span>
          </span>
        ))}
      </div>
    )
  }

  return (
    <div
      style={{
        background: 'var(--card)',
        color: 'var(--card-foreground)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius)',
        width: 196,
        boxShadow: halo,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          padding: '8px 10px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
        }}
      >
        <span style={{ fontSize: 13, fontWeight: 600 }}>Categories</span>
        {total !== undefined && (
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              color: 'var(--muted-foreground)',
            }}
          >
            n = {total.toLocaleString()}
          </span>
        )}
      </div>

      <div style={{ padding: '6px 10px' }}>
        {categories.map((cat) => (
          <div
            key={cat.label}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '5px 0',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span
                style={{
                  width: 10,
                  height: 10,
                  borderRadius: 999,
                  background: `var(${cat.colorVar})`,
                  boxShadow: '0 0 0 1.5px var(--background)',
                  flexShrink: 0,
                }}
              />
              <span style={{ fontSize: 12 }}>{cat.label}</span>
            </div>
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 11,
                color: 'var(--muted-foreground)',
                fontVariantNumeric: 'tabular-nums',
              }}
            >
              {cat.count}
            </span>
          </div>
        ))}
      </div>

      <div
        style={{
          padding: '6px 10px',
          borderTop: '1px solid var(--border)',
          background: 'var(--muted)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: 11,
        }}
      >
        {status && <span style={{ color: 'var(--muted-foreground)' }}>{status}</span>}
        {lastUpdated && <span style={{ color: 'var(--muted-foreground)' }}>{lastUpdated}</span>}
      </div>
    </div>
  )
}
