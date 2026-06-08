import React from 'react'
import { Search } from 'lucide-react'
import { MapSurfacePlaceholder } from './MapLoadingState'

interface MapEmptyStateProps {
  message?: string
  description?: string
  onResetFilters?: () => void
  onZoomToFit?: () => void
}

export function MapEmptyState({
  message = 'No incidents in view',
  description = 'No incidents match the current filters in this viewport. Try widening the date range or zooming out to the Upper Valley.',
  onResetFilters,
  onZoomToFit,
}: MapEmptyStateProps) {
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <MapSurfacePlaceholder style={{ position: 'absolute', inset: 0, opacity: 0.5 }} />

      <div
        style={{
          position: 'absolute',
          left: '50%', top: '50%',
          transform: 'translate(-50%, -50%)',
          background: 'var(--popover)',
          color: 'var(--popover-foreground)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius)',
          padding: '20px 22px',
          boxShadow: '0 10px 24px -8px rgba(0,0,0,0.18), 0 0 0 4px var(--background)',
          width: 280,
          textAlign: 'center',
        }}
      >
        <div
          style={{
            width: 36, height: 36,
            borderRadius: 999,
            margin: '0 auto 10px',
            display: 'grid', placeItems: 'center',
            background: 'var(--muted)',
            color: 'var(--muted-foreground)',
          }}
        >
          <Search size={16} />
        </div>
        <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>{message}</div>
        <div style={{ fontSize: 11, color: 'var(--muted-foreground)', marginBottom: 12, lineHeight: 1.5 }}>
          {description}
        </div>
        <div style={{ display: 'flex', gap: 6, justifyContent: 'center' }}>
          {onResetFilters && (
            <button
              onClick={onResetFilters}
              style={{ height: 28, padding: '0 10px', borderRadius: 'calc(var(--radius) - 4px)', border: '1px solid var(--border)', background: 'transparent', color: 'var(--foreground)', fontSize: 12, fontWeight: 500, cursor: 'pointer' }}
            >
              Reset filters
            </button>
          )}
          {onZoomToFit && (
            <button
              onClick={onZoomToFit}
              style={{ height: 28, padding: '0 10px', borderRadius: 'calc(var(--radius) - 4px)', border: 'none', background: 'var(--primary)', color: 'var(--primary-foreground)', fontSize: 12, fontWeight: 500, cursor: 'pointer' }}
            >
              Zoom to fit
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

