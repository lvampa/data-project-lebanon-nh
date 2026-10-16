import React from 'react'
import { X } from 'lucide-react'
import type { MarkerCategory } from './IncidentMarker'

interface PopupField {
  label: string
  value: React.ReactNode
}

interface IncidentPopupProps {
  title: string
  incidentId: string
  category?: MarkerCategory
  fields?: PopupField[]
  status?: string
  attribution?: string
  onClose?: () => void
  onViewRecord?: () => void
}

const CHART_VARS: Record<MarkerCategory, string> = {
  1: 'var(--chart-1)',
  2: 'var(--chart-2)',
  3: 'var(--chart-3)',
  4: 'var(--chart-4)',
  5: 'var(--chart-5)',
}

const DEFAULT_FIELDS: PopupField[] = [
  { label: 'Reported', value: '14 Jan 2026, 03:42' },
  { label: 'Type', value: 'Residential · single-family' },
  { label: 'Address', value: '184 Mascoma Street' },
  { label: 'Response', value: 'LFD · Engine 1, Engine 2, Tower 1' },
]

export function IncidentPopup({
  title,
  incidentId,
  category = 1,
  fields = DEFAULT_FIELDS,
  status,
  attribution,
  onClose,
  onViewRecord,
}: IncidentPopupProps) {
  const color = CHART_VARS[category]

  return (
    <div style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'center' }}>
      {/* Popup card */}
      <div
        style={{
          background: 'var(--popover)',
          color: 'var(--popover-foreground)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius)',
          width: 280,
          boxShadow: '0 10px 24px -8px rgba(0,0,0,0.18), 0 0 0 4px var(--background)',
          overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            padding: '10px 12px',
            borderBottom: '1px solid var(--border)',
            gap: 8,
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span
                style={{ width: 8, height: 8, borderRadius: 999, background: color, flexShrink: 0 }}
              />
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--foreground)' }}>
                {title}
              </span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>{incidentId}</div>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              title="Close"
              style={{
                width: 24,
                height: 24,
                borderRadius: 'calc(var(--radius) - 4px)',
                border: 'none',
                background: 'transparent',
                color: 'var(--foreground)',
                display: 'grid',
                placeItems: 'center',
                cursor: 'pointer',
                flexShrink: 0,
              }}
            >
              <X size={12} />
            </button>
          )}
        </div>

        {/* Key-value body */}
        <div
          style={{
            padding: 12,
            display: 'grid',
            gridTemplateColumns: 'auto 1fr',
            rowGap: 6,
            columnGap: 12,
            fontSize: 12,
          }}
        >
          {fields.map((f, i) => (
            <React.Fragment key={i}>
              <div style={{ color: 'var(--muted-foreground)', whiteSpace: 'nowrap' }}>
                {f.label}
              </div>
              <div>{f.value}</div>
            </React.Fragment>
          ))}
          {status && (
            <>
              <div style={{ color: 'var(--muted-foreground)' }}>Status</div>
              <div>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    height: 18,
                    padding: '0 6px',
                    borderRadius: 999,
                    fontSize: 10,
                    fontWeight: 600,
                    background: 'var(--primary)',
                    color: 'var(--primary-foreground)',
                  }}
                >
                  {status}
                </span>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: '8px 12px',
            borderTop: '1px solid var(--border)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            background: 'var(--muted)',
          }}
        >
          {attribution && (
            <span style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>{attribution}</span>
          )}
          {onViewRecord && (
            <button
              onClick={onViewRecord}
              style={{
                height: 28,
                padding: '0 10px',
                borderRadius: 'calc(var(--radius) - 4px)',
                border: '1px solid var(--border)',
                background: 'transparent',
                color: 'var(--foreground)',
                fontSize: 12,
                fontWeight: 500,
                cursor: 'pointer',
              }}
            >
              View full record →
            </button>
          )}
        </div>
      </div>

      {/* Pointer tail */}
      <div
        style={{
          width: 0,
          height: 0,
          borderLeft: '8px solid transparent',
          borderRight: '8px solid transparent',
          borderTop: '8px solid var(--popover)',
          filter: 'drop-shadow(0 1px 0 var(--border))',
          marginTop: -1,
        }}
      />

      {/* Anchor marker */}
      <div
        style={{
          marginTop: -4,
          width: 22,
          height: 22,
          borderRadius: 999,
          background: 'var(--background)',
          boxShadow: '0 0 0 2px var(--foreground), 0 1px 3px rgba(0,0,0,0.25)',
          display: 'grid',
          placeItems: 'center',
        }}
      >
        <div style={{ width: 12, height: 12, borderRadius: 999, background: color }} />
      </div>
    </div>
  )
}
