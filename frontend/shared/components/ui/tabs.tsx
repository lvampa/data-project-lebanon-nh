'use client'
import React, { useState } from 'react'
import { cn } from '../../lib/utils'

export interface TabItem {
  id: string
  label: string
  count?: number
}

interface TabsProps {
  items: TabItem[]
  value?: string
  defaultValue?: string
  onChange?: (id: string) => void
  variant?: 'underline' | 'pill'
  className?: string
}

export function Tabs({
  items,
  value: controlledValue,
  defaultValue,
  onChange,
  variant = 'underline',
  className,
}: TabsProps) {
  const [internal, setInternal] = useState(defaultValue ?? items[0]?.id)
  const isControlled = controlledValue !== undefined
  const active = isControlled ? controlledValue : internal

  const select = (id: string) => {
    if (!isControlled) setInternal(id)
    onChange?.(id)
  }

  return (
    <div
      role="tablist"
      className={cn(
        'inline-flex',
        variant === 'underline' && 'gap-1 border-b border-border',
        variant === 'pill' &&
          'gap-1 rounded-[calc(var(--radius)-2px)] border border-border bg-muted p-[3px]',
        className,
      )}
    >
      {items.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={tab.id === active}
          onClick={() => select(tab.id)}
          className={cn(
            'inline-flex items-center gap-1.5 text-[13px] font-medium transition-colors',
            'outline-none focus-visible:ring-2 focus-visible:ring-ring',
            // underline variant
            variant === 'underline' && [
              'rounded-none border-b-2 border-transparent px-3 py-2.5 text-muted-foreground hover:text-foreground',
              '-mb-px',
              tab.id === active && 'border-primary text-foreground',
            ],
            // pill variant
            variant === 'pill' && [
              'rounded-[calc(var(--radius)-4px)] px-3 py-[5px] text-muted-foreground hover:text-foreground',
              tab.id === active && 'bg-background text-foreground shadow-sm',
            ],
          )}
        >
          <span>{tab.label}</span>
          {tab.count !== undefined && (
            <span className="rounded-full border border-border bg-background px-1.5 py-px font-mono text-[11px] text-muted-foreground">
              {tab.count}
            </span>
          )}
        </button>
      ))}
    </div>
  )
}
