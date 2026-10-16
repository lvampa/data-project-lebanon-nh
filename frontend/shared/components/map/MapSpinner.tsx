import React from 'react'

interface MapSpinnerProps {
  size?: number
}

export function MapSpinner({ size = 18 }: MapSpinnerProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" style={{ display: 'block', flexShrink: 0 }}>
      <circle
        cx="12"
        cy="12"
        r="9"
        fill="none"
        stroke="color-mix(in oklch, var(--foreground) 12%, transparent)"
        strokeWidth="2.5"
      />
      <path
        d="M12 3 a9 9 0 0 1 9 9"
        fill="none"
        stroke="var(--foreground)"
        strokeWidth="2.5"
        strokeLinecap="round"
        style={{ transformOrigin: '12px 12px', animation: 'spin 0.9s linear infinite' }}
      />
    </svg>
  )
}
