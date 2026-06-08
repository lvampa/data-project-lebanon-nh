import React from 'react'
import { cn } from '../../lib/utils'

type Variant = 'primary' | 'success' | 'warning' | 'danger' | 'neutral'

interface ProgressBarProps {
  value: number
  max?: number
  variant?: Variant
  showValue?: boolean
  label?: string
  size?: 'sm' | 'md'
  className?: string
}

const fills: Record<Variant, string> = {
  primary: 'bg-primary',
  success: 'bg-[oklch(0.620_0.150_155)]',
  warning: 'bg-[oklch(0.769_0.188_70.08)]',
  danger:  'bg-destructive',
  neutral: 'bg-muted-foreground',
}

export function ProgressBar({
  value,
  max = 100,
  variant = 'primary',
  showValue = false,
  label,
  size = 'md',
  className,
}: ProgressBarProps) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100))

  return (
    <div className={cn('flex flex-col gap-1.5', className)}>
      {(label || showValue) && (
        <div className="flex justify-between text-xs">
          {label && <span className="text-muted-foreground">{label}</span>}
          {showValue && (
            <span className="font-mono tabular-nums text-muted-foreground">
              {value.toLocaleString()} / {max.toLocaleString()}
            </span>
          )}
        </div>
      )}
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={value}
        className={cn('w-full overflow-hidden rounded-full bg-muted', size === 'sm' ? 'h-1' : 'h-2')}
      >
        <div
          className={cn('h-full rounded-full transition-[width] duration-200', fills[variant])}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}
