import React from 'react'
import { cn } from '../../lib/utils'

type Variant = 'ghost' | 'outline' | 'primary'
type Size = 'sm' | 'md' | 'lg'

interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  label: string
}

const dims: Record<Size, string> = {
  sm: 'size-7',
  md: 'size-8',
  lg: 'size-10',
}

const iconSizes: Record<Size, string> = {
  sm: '[&_svg]:size-3.5',
  md: '[&_svg]:size-4',
  lg: '[&_svg]:size-[18px]',
}

const variants: Record<Variant, string> = {
  ghost:   'bg-transparent border-transparent text-muted-foreground hover:bg-muted hover:text-foreground',
  outline: 'bg-transparent border-border text-foreground hover:bg-muted',
  primary: 'bg-primary border-transparent text-primary-foreground hover:bg-primary/80',
}

export function IconButton({
  variant = 'ghost',
  size = 'md',
  label,
  className,
  children,
  ...props
}: IconButtonProps) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      className={cn(
        'inline-flex items-center justify-center rounded-[calc(var(--radius)-4px)] border',
        'transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        'disabled:pointer-events-none disabled:opacity-50',
        dims[size],
        iconSizes[size],
        variants[variant],
        className,
      )}
      {...props}
    >
      {children}
    </button>
  )
}
