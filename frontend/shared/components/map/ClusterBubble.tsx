import React from 'react'

interface ClusterBubbleProps {
  count: number
  size?: 'sm' | 'md' | 'lg'
}

const DIMS = { sm: 28, md: 36, lg: 44 }
const FONT = { sm: 11, md: 13, lg: 15 }

export function ClusterBubble({ count, size = 'md' }: ClusterBubbleProps) {
  const dim = DIMS[size]
  const fs = FONT[size]

  return (
    <div
      style={{
        width: dim,
        height: dim,
        borderRadius: 999,
        background: 'var(--background)',
        boxShadow:
          '0 0 0 1px color-mix(in oklch, var(--foreground) 15%, transparent), 0 1px 3px rgba(0,0,0,0.18)',
        display: 'grid',
        placeItems: 'center',
        position: 'relative',
      }}
    >
      {/* Concentric soft ring */}
      <div
        style={{
          position: 'absolute',
          inset: 4,
          borderRadius: 999,
          background: 'color-mix(in oklch, var(--primary) 18%, transparent)',
        }}
      />
      <span
        style={{
          position: 'relative',
          zIndex: 1,
          fontSize: fs,
          fontWeight: 700,
          color: 'var(--foreground)',
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {count}
      </span>
    </div>
  )
}
