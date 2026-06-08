import React from 'react'
import { X } from 'lucide-react'
import { cn } from '../../lib/utils'

interface TagProps {
  children: React.ReactNode
  onRemove?: () => void
  icon?: React.ReactNode
  className?: string
}

export function Tag({ children, onRemove, icon, className }: TagProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 h-6 px-2',
        'rounded-sm border border-border bg-background',
        'text-xs text-muted-foreground font-sans leading-none',
        className,
      )}
    >
      {icon && <span className="inline-flex items-center text-muted-foreground [&_svg]:size-3">{icon}</span>}
      <span>{children}</span>
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          aria-label="Remove"
          className="inline-flex items-center justify-center size-4 rounded-[2px] transition-colors hover:bg-muted hover:text-foreground"
        >
          <X size={10} />
        </button>
      )}
    </span>
  )
}
