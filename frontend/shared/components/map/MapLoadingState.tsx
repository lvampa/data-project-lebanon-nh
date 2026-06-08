import React from 'react'
import { MapSpinner } from './MapSpinner'

interface MapLoadingStateProps {
  progress?: string
}

export function MapLoadingState({ progress = '3 of 12 quadrants · ~2 s' }: MapLoadingStateProps) {
  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
      {/* Dimmed map surface */}
      <MapSurfacePlaceholder style={{ position: 'absolute', inset: 0, opacity: 0.55 }} />

      {/* Shimmer sweep */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background:
            'linear-gradient(110deg, transparent 30%, color-mix(in oklch, var(--foreground) 6%, transparent) 50%, transparent 70%)',
          backgroundSize: '200% 100%',
          animation: 'shimmer 1.6s ease-in-out infinite',
          pointerEvents: 'none',
        }}
      />

      {/* Skeleton card placeholders */}
      <div
        style={{
          position: 'absolute', top: 16, left: 16,
          width: 180, height: 36,
          borderRadius: 'var(--radius)',
          background: 'color-mix(in oklch, var(--foreground) 10%, transparent)',
        }}
      />
      <div
        style={{
          position: 'absolute', top: 16, right: 16,
          width: 180, height: 120,
          borderRadius: 'var(--radius)',
          background: 'color-mix(in oklch, var(--foreground) 10%, transparent)',
        }}
      />

      {/* Loading badge */}
      <div
        style={{
          position: 'absolute',
          left: '50%', top: '50%',
          transform: 'translate(-50%, -50%)',
          background: 'var(--popover)',
          color: 'var(--popover-foreground)',
          border: '1px solid var(--border)',
          borderRadius: 'var(--radius)',
          padding: '10px 14px',
          boxShadow: '0 10px 24px -8px rgba(0,0,0,0.18), 0 0 0 4px var(--background)',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          whiteSpace: 'nowrap',
        }}
      >
        <MapSpinner size={16} />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          <span style={{ fontSize: 13, fontWeight: 600 }}>Loading tiles</span>
          <span style={{ fontSize: 11, color: 'var(--muted-foreground)' }}>{progress}</span>
        </div>
      </div>
    </div>
  )
}

export function MapSurfacePlaceholder({ style }: { style?: React.CSSProperties }) {
  return (
    <div
      style={{
        background:
          'radial-gradient(circle at 12px 12px, color-mix(in oklch, var(--foreground) 12%, transparent) 1px, transparent 1.5px), var(--muted)',
        backgroundSize: '24px 24px',
        ...style,
      }}
    />
  )
}
