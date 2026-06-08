import React from 'react'

export type MarkerState = 'default' | 'hover' | 'selected' | 'muted'
export type MarkerCategory = 1 | 2 | 3 | 4 | 5

const CHART_VARS: Record<MarkerCategory, string> = {
  1: 'var(--chart-1)',
  2: 'var(--chart-2)',
  3: 'var(--chart-3)',
  4: 'var(--chart-4)',
  5: 'var(--chart-5)',
}

interface IncidentMarkerProps {
  category?: MarkerCategory
  state?: MarkerState
}

export function IncidentMarker({ category = 1, state = 'default' }: IncidentMarkerProps) {
  const color = CHART_VARS[category]
  const haloStroke = 'color-mix(in oklch, var(--foreground) 15%, transparent)'

  const outerSize = state === 'selected' ? 24 : state === 'hover' ? 22 : 18
  const innerSize = state === 'selected' ? 12 : 10
  const opacity = state === 'muted' ? 0.45 : 1

  const boxShadow =
    state === 'selected'
      ? `0 0 0 2px var(--foreground), 0 1px 3px rgba(0,0,0,0.25)`
      : `0 0 0 1px ${haloStroke}, 0 1px 2px rgba(0,0,0,0.18)`

  return (
    <div
      style={{
        position: 'relative',
        display: 'inline-flex',
        flexDirection: 'column',
        alignItems: 'center',
        width: outerSize + 8,
        height: outerSize + (state === 'selected' ? 24 : 8),
      }}
    >
      {/* Selected pin tail */}
      {state === 'selected' && (
        <div
          style={{
            position: 'absolute',
            bottom: 0,
            left: '50%',
            transform: 'translateX(-50%)',
            width: 0,
            height: 0,
            borderLeft: '5px solid transparent',
            borderRight: '5px solid transparent',
            borderTop: `8px solid var(--background)`,
            filter: `drop-shadow(0 1px 0 ${haloStroke})`,
          }}
        />
      )}
      {/* Halo ring */}
      <div
        style={{
          width: outerSize,
          height: outerSize,
          borderRadius: 999,
          background: 'var(--background)',
          boxShadow,
          display: 'grid',
          placeItems: 'center',
          opacity,
        }}
      >
        {/* Category dot */}
        <div
          style={{
            width: innerSize,
            height: innerSize,
            borderRadius: 999,
            background: color,
          }}
        />
      </div>
    </div>
  )
}
