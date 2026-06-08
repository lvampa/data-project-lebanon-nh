import React, { useState } from 'react'
import { Layers, Search, ChevronDown } from 'lucide-react'

export interface FilterCategory {
  label: string
  count: number
  enabled: boolean
  colorVar: string
}

const DEFAULT_CATEGORIES: FilterCategory[] = [
  { label: 'Fire',    count: 38,  enabled: true,  colorVar: '--chart-1' },
  { label: 'Medical', count: 214, enabled: true,  colorVar: '--chart-2' },
  { label: 'Traffic', count: 96,  enabled: true,  colorVar: '--chart-3' },
  { label: 'Utility', count: 12,  enabled: false, colorVar: '--chart-4' },
  { label: 'Police',  count: 151, enabled: false, colorVar: '--chart-5' },
]

interface MapFilterPanelProps {
  categories?: FilterCategory[]
  searchValue?: string
  onSearchChange?: (value: string) => void
  onCategoryToggle?: (index: number, enabled: boolean) => void
  dateFrom?: string
  dateTo?: string
  onReset?: () => void
  onApply?: () => void
  defaultCollapsed?: boolean
  activeCount?: number
}

export function MapFilterPanel({
  categories = DEFAULT_CATEGORIES,
  searchValue = '',
  onSearchChange,
  onCategoryToggle,
  dateFrom = '2024-06-01',
  dateTo = '2026-01-14',
  onReset,
  onApply,
  defaultCollapsed = false,
  activeCount,
}: MapFilterPanelProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed)
  const enabledCount = activeCount ?? categories.filter((c) => c.enabled).length

  return (
    <div
      style={{
        background: 'var(--card)',
        color: 'var(--card-foreground)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius)',
        width: 264,
        boxShadow: '0 8px 24px -10px rgba(0,0,0,0.18), 0 0 0 4px var(--background)',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '10px 12px',
          borderBottom: collapsed ? 'none' : '1px solid var(--border)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Layers size={14} />
          <span style={{ fontSize: 13, fontWeight: 600 }}>Filters</span>
          {enabledCount > 0 && (
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                height: 18,
                padding: '0 6px',
                borderRadius: 999,
                fontSize: 10,
                fontWeight: 600,
                background: 'var(--secondary)',
                color: 'var(--secondary-foreground)',
                border: '1px solid color-mix(in oklch, var(--foreground) 8%, transparent)',
              }}
            >
              {enabledCount} active
            </span>
          )}
        </div>
        <button
          onClick={() => setCollapsed((v) => !v)}
          title={collapsed ? 'Expand' : 'Collapse'}
          style={{
            width: 28,
            height: 28,
            border: 'none',
            borderRadius: 'calc(var(--radius) - 4px)',
            background: 'transparent',
            color: 'var(--foreground)',
            display: 'grid',
            placeItems: 'center',
            cursor: 'pointer',
            transform: collapsed ? 'rotate(-90deg)' : 'none',
            transition: 'transform 150ms',
          }}
        >
          <ChevronDown size={12} />
        </button>
      </div>

      {!collapsed && (
        <>
          {/* Search */}
          <div style={{ padding: 12, borderBottom: '1px solid var(--border)' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                height: 30,
                padding: '0 8px',
                background: 'var(--background)',
                border: '1px solid var(--input)',
                borderRadius: 'calc(var(--radius) - 4px)',
                fontSize: 12,
              }}
            >
              <Search size={12} style={{ color: 'var(--muted-foreground)', flexShrink: 0 }} />
              <input
                value={searchValue}
                onChange={(e) => onSearchChange?.(e.target.value)}
                placeholder="Address, ID, type…"
                style={{
                  flex: 1,
                  minWidth: 0,
                  border: 'none',
                  outline: 'none',
                  background: 'transparent',
                  color: 'var(--foreground)',
                  fontSize: 'inherit',
                }}
              />
            </div>
          </div>

          {/* Categories */}
          <div style={{ padding: '8px 12px 12px', borderBottom: '1px solid var(--border)' }}>
            <div style={{ fontSize: 10, color: 'var(--muted-foreground)', textTransform: 'uppercase', letterSpacing: '0.06em', padding: '4px 0 2px' }}>
              Categories
            </div>
            {categories.map((cat, i) => (
              <div key={cat.label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 0' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                  <span style={{ width: 10, height: 10, borderRadius: 999, background: `var(${cat.colorVar})`, boxShadow: '0 0 0 1.5px var(--background)', flexShrink: 0 }} />
                  <span style={{ fontSize: 12, color: 'var(--foreground)' }}>{cat.label}</span>
                  <code style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--muted-foreground)' }}>{cat.colorVar}</code>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 11, color: 'var(--muted-foreground)', fontVariantNumeric: 'tabular-nums' }}>{cat.count}</span>
                  <Switch
                    on={cat.enabled}
                    onChange={(v) => onCategoryToggle?.(i, v)}
                  />
                </div>
              </div>
            ))}
          </div>

          {/* Date range */}
          <div style={{ padding: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
              <span style={{ fontSize: 10, color: 'var(--muted-foreground)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Date range</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--muted-foreground)' }}>
                {dateFrom.slice(0, 4)} — {dateTo.slice(0, 4)}
              </span>
            </div>

            {/* Range track (visual only) */}
            <div style={{ position: 'relative', height: 6, background: 'var(--muted)', borderRadius: 999, margin: '8px 6px' }}>
              <div style={{ position: 'absolute', left: '22%', right: '12%', top: 0, bottom: 0, background: 'var(--primary)', borderRadius: 999 }} />
              {[22, 88].map((pct) => (
                <div
                  key={pct}
                  style={{
                    position: 'absolute',
                    left: `${pct}%`,
                    top: -4,
                    width: 14,
                    height: 14,
                    borderRadius: 999,
                    background: 'var(--background)',
                    boxShadow: '0 0 0 1.5px var(--primary), 0 1px 2px rgba(0,0,0,0.18)',
                    transform: 'translateX(-50%)',
                  }}
                />
              ))}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 6, marginTop: 12, alignItems: 'center' }}>
              <DateInput value={dateFrom} />
              <span style={{ color: 'var(--muted-foreground)', fontSize: 11 }}>—</span>
              <DateInput value={dateTo} />
            </div>
          </div>

          {/* Footer */}
          <div
            style={{
              padding: '8px 12px',
              borderTop: '1px solid var(--border)',
              background: 'var(--muted)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <button
              onClick={onReset}
              style={{ height: 28, padding: '0 10px', borderRadius: 'calc(var(--radius) - 4px)', border: '1px solid transparent', background: 'transparent', color: 'var(--foreground)', fontSize: 12, fontWeight: 500, cursor: 'pointer' }}
            >
              Reset
            </button>
            <button
              onClick={onApply}
              style={{ height: 28, padding: '0 10px', borderRadius: 'calc(var(--radius) - 4px)', border: 'none', background: 'var(--primary)', color: 'var(--primary-foreground)', fontSize: 12, fontWeight: 500, cursor: 'pointer' }}
            >
              Apply
            </button>
          </div>
        </>
      )}
    </div>
  )
}

function Switch({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      role="switch"
      aria-checked={on}
      onClick={() => onChange(!on)}
      style={{
        width: 32,
        height: 18,
        borderRadius: 999,
        background: on ? 'var(--primary)' : 'var(--input)',
        position: 'relative',
        border: 'none',
        padding: 0,
        cursor: 'pointer',
        transition: 'background 150ms',
        flexShrink: 0,
      }}
    >
      <span
        style={{
          position: 'absolute',
          top: 2,
          left: 2,
          width: 14,
          height: 14,
          borderRadius: 999,
          background: 'var(--background)',
          transform: on ? 'translateX(14px)' : 'none',
          transition: 'transform 150ms',
        }}
      />
    </button>
  )
}

function DateInput({ value }: { value: string }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        height: 30,
        padding: '0 8px',
        background: 'var(--background)',
        border: '1px solid var(--input)',
        borderRadius: 'calc(var(--radius) - 4px)',
        fontSize: 12,
        fontFamily: 'var(--font-mono)',
      }}
    >
      <input
        defaultValue={value}
        style={{ flex: 1, minWidth: 0, border: 'none', outline: 'none', background: 'transparent', color: 'var(--foreground)', fontSize: 'inherit', fontFamily: 'inherit' }}
      />
    </div>
  )
}

