'use client'
import React, { useId, useState } from 'react'
import { cn } from '../../lib/utils'

interface SwitchProps {
  checked?: boolean
  defaultChecked?: boolean
  onCheckedChange?: (checked: boolean) => void
  disabled?: boolean
  label?: string
  description?: string
  size?: 'sm' | 'md'
  className?: string
  name?: string
}

export function Switch({
  checked: controlledChecked,
  defaultChecked = false,
  onCheckedChange,
  disabled = false,
  label,
  description,
  size = 'md',
  className,
  name,
}: SwitchProps) {
  const id = useId()
  const [internal, setInternal] = useState(defaultChecked)
  const isControlled = controlledChecked !== undefined
  const on = isControlled ? controlledChecked : internal

  const w = size === 'sm' ? 28 : 36
  const h = size === 'sm' ? 16 : 20
  const knob = h - 4
  const travel = w - knob - 4

  const toggle = () => {
    if (disabled) return
    const next = !on
    if (!isControlled) setInternal(next)
    onCheckedChange?.(next)
  }

  return (
    <label
      htmlFor={id}
      className={cn(
        'inline-flex items-start gap-2.5',
        disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer',
        className,
      )}
    >
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={on}
        disabled={disabled}
        name={name}
        onClick={toggle}
        className={cn(
          'relative shrink-0 rounded-full border-none p-0 outline-none transition-colors duration-150',
          'focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
          'disabled:cursor-not-allowed',
          on ? 'bg-primary' : 'bg-input',
        )}
        style={{ width: w, height: h }}
      >
        <span
          className="block rounded-full bg-white shadow-sm transition-transform duration-150"
          style={{
            width: knob,
            height: knob,
            position: 'absolute',
            top: 2,
            left: 2,
            transform: on ? `translateX(${travel}px)` : 'translateX(0)',
          }}
        />
      </button>
      {(label || description) && (
        <span className="flex flex-col gap-0.5 pt-px">
          {label && <span className="text-[13px] font-medium leading-tight text-foreground">{label}</span>}
          {description && <span className="text-xs text-muted-foreground">{description}</span>}
        </span>
      )}
    </label>
  )
}
