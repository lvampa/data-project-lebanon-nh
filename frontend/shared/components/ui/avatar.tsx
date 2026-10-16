import React from 'react'
import { cn } from '../../lib/utils'

interface AvatarProps {
  src?: string
  name?: string
  size?: number
  bg?: string
  className?: string
}

const SHADES = [
  'oklch(0.371 0 0)',
  'oklch(0.440 0 0)',
  'oklch(0.269 0 0)',
  'oklch(0.556 0 0)',
  'oklch(0.205 0 0)',
]

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join('')
}

function colorFor(name: string) {
  const hash = [...name].reduce((a, c) => a + c.charCodeAt(0), 0)
  return SHADES[hash % SHADES.length]
}

export function Avatar({ src, name = '?', size = 32, bg, className }: AvatarProps) {
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-full overflow-hidden font-medium text-white',
        className,
      )}
      style={{
        width: size,
        height: size,
        fontSize: Math.round(size * 0.42),
        background: src ? undefined : (bg ?? colorFor(name)),
        border: '1px solid color-mix(in oklch, var(--foreground) 6%, transparent)',
      }}
      aria-label={name}
    >
      {src ? (
        <img src={src} alt={name} className="w-full h-full object-cover" />
      ) : (
        initials(name) || '·'
      )}
    </span>
  )
}
