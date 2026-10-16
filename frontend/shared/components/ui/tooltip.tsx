'use client'
import React from 'react'
import { cn } from '../../lib/utils'

type TooltipSide = 'top' | 'bottom' | 'left' | 'right'

interface TooltipProps {
  content: React.ReactNode
  side?: TooltipSide
  children: React.ReactNode
  className?: string
}

const positionClasses: Record<TooltipSide, string> = {
  top: 'bottom-[calc(100%+6px)] left-1/2 -translate-x-1/2',
  bottom: 'top-[calc(100%+6px)] left-1/2 -translate-x-1/2',
  left: 'right-[calc(100%+6px)] top-1/2 -translate-y-1/2',
  right: 'left-[calc(100%+6px)] top-1/2 -translate-y-1/2',
}

export function Tooltip({ content, side = 'top', children, className }: TooltipProps) {
  return (
    <span className={cn('relative inline-flex', className)}>
      {children}
      <span
        role="tooltip"
        className={cn(
          'pointer-events-none absolute z-50 whitespace-nowrap rounded-[calc(var(--radius)-4px)]',
          'bg-foreground px-2 py-1 text-[11px] font-medium text-background shadow-md',
          'opacity-0 transition-opacity duration-150',
          '[.group:hover_&]:opacity-100',
          'group-hover:opacity-100',
          positionClasses[side],
        )}
      >
        {content}
      </span>
    </span>
  )
}

// Convenience wrapper that adds the group class to the trigger element
export function TooltipTrigger({ content, side = 'top', children }: TooltipProps) {
  return (
    <span className="group relative inline-flex">
      {children}
      <span
        role="tooltip"
        className={cn(
          'pointer-events-none absolute z-50 whitespace-nowrap rounded-[calc(var(--radius)-4px)]',
          'bg-foreground px-2 py-1 text-[11px] font-medium text-background shadow-md',
          'opacity-0 transition-opacity duration-150 group-hover:opacity-100',
          positionClasses[side],
        )}
      >
        {content}
      </span>
    </span>
  )
}
