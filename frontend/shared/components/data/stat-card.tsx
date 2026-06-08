import React from 'react'
import { cn } from '../../lib/utils'
import { Sparkline } from './sparkline'

interface StatCardProps {
  label: string
  value: React.ReactNode
  unit?: string
  delta?: number
  deltaLabel?: string
  invertDeltaPolarity?: boolean
  sparkline?: number[]
  footnote?: string
  className?: string
}

export function StatCard({
  label,
  value,
  unit,
  delta,
  deltaLabel = 'vs. previous',
  invertDeltaPolarity = false,
  sparkline,
  footnote,
  className,
}: StatCardProps) {
  const hasDelta = typeof delta === 'number'
  const positive = hasDelta && delta >= 0
  const good = invertDeltaPolarity ? !positive : positive

  return (
    <div
      className={cn(
        'flex flex-col gap-1.5 rounded-lg border border-border bg-card p-4',
        className,
      )}
    >
      <div className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>

      <div className="flex items-baseline gap-1.5">
        <span
          className="text-[32px] font-medium leading-none tabular-nums tracking-tight text-foreground"
          style={{ fontFamily: 'var(--font-display)' }}
        >
          {value}
        </span>
        {unit && (
          <span className="text-sm text-muted-foreground">{unit}</span>
        )}
      </div>

      <div className="mt-0.5 flex items-center justify-between gap-2">
        <div>
          {hasDelta && (
            <span
              className={cn(
                'inline-flex items-center gap-1 font-mono text-xs font-medium tabular-nums',
                good ? 'text-[oklch(0.620_0.150_155)]' : 'text-destructive',
              )}
            >
              <span>{positive ? '▲' : '▼'}</span>
              <span>{Math.abs(delta).toFixed(1)}%</span>
              <span className="ml-1 font-sans text-[11px] text-muted-foreground">{deltaLabel}</span>
            </span>
          )}
        </div>
        {sparkline && sparkline.length > 1 && (
          <Sparkline
            values={sparkline}
            width={120}
            height={36}
            color="var(--foreground)"
            filled
            showLast
          />
        )}
      </div>

      {footnote && (
        <div className="mt-1 text-[11px] text-muted-foreground">{footnote}</div>
      )}
    </div>
  )
}
