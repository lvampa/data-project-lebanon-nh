import React from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

interface MapErrorStateProps {
  title?: string
  message?: string
  errorDetail?: string
  onRetry?: () => void
  onViewList?: () => void
}

export function MapErrorState({
  title = 'Map failed to load',
  message = "Couldn't reach the tile server. Check your connection and retry — the rest of the incidents catalogue is still available below.",
  errorDetail,
  onRetry,
  onViewList,
}: MapErrorStateProps) {
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {/* Hatched background — map failed, no surface to show */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background:
            'repeating-linear-gradient(135deg, transparent 0 11px, color-mix(in oklch, var(--foreground) 4%, transparent) 11px 12px)',
        }}
      />

      <div
        style={{
          position: 'absolute',
          left: '50%',
          top: '50%',
          transform: 'translate(-50%, -50%)',
          background: 'var(--popover)',
          color: 'var(--popover-foreground)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius)',
          padding: '18px 22px',
          boxShadow: '0 10px 24px -8px rgba(0,0,0,0.18), 0 0 0 4px var(--background)',
          width: 300,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 999,
              flexShrink: 0,
              display: 'grid',
              placeItems: 'center',
              background: 'color-mix(in oklch, var(--destructive) 14%, transparent)',
              color: 'var(--destructive)',
            }}
          >
            <AlertTriangle size={16} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 2 }}>{title}</div>
            <div
              style={{
                fontSize: 11,
                color: 'var(--muted-foreground)',
                lineHeight: 1.5,
                marginBottom: 10,
              }}
            >
              {message}
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              {onRetry && (
                <button
                  onClick={onRetry}
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
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                  }}
                >
                  <RefreshCw size={12} /> Retry
                </button>
              )}
              {onViewList && (
                <button
                  onClick={onViewList}
                  style={{
                    height: 28,
                    padding: '0 10px',
                    borderRadius: 'calc(var(--radius) - 4px)',
                    border: '1px solid transparent',
                    background: 'transparent',
                    color: 'var(--foreground)',
                    fontSize: 12,
                    fontWeight: 500,
                    cursor: 'pointer',
                  }}
                >
                  View list instead
                </button>
              )}
            </div>
          </div>
        </div>

        {errorDetail && (
          <div
            style={{
              marginTop: 12,
              paddingTop: 10,
              borderTop: '1px solid var(--border)',
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              color: 'var(--muted-foreground)',
              display: 'flex',
              justifyContent: 'space-between',
            }}
          >
            <span>{errorDetail}</span>
          </div>
        )}
      </div>
    </div>
  )
}
