'use client'
import React, { useId, useRef, useEffect, useState } from 'react'
import { Check, Minus } from 'lucide-react'
import { cn } from '../../lib/utils'

interface CheckboxProps {
  checked?: boolean
  defaultChecked?: boolean
  indeterminate?: boolean
  onCheckedChange?: (checked: boolean) => void
  disabled?: boolean
  label?: string
  description?: string
  id?: string
  className?: string
  name?: string
}

export function Checkbox({
  checked: controlledChecked,
  defaultChecked = false,
  indeterminate = false,
  onCheckedChange,
  disabled = false,
  label,
  description,
  id: providedId,
  className,
  name,
}: CheckboxProps) {
  const autoId = useId()
  const id = providedId ?? autoId
  const inputRef = useRef<HTMLInputElement>(null)
  const [internal, setInternal] = useState(defaultChecked)
  const isControlled = controlledChecked !== undefined
  const checked = isControlled ? controlledChecked : internal

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.indeterminate = indeterminate && !checked
    }
  }, [indeterminate, checked])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const next = e.target.checked
    if (!isControlled) setInternal(next)
    onCheckedChange?.(next)
  }

  const isIndeterminate = indeterminate && !checked

  return (
    <label
      htmlFor={id}
      className={cn(
        'inline-flex items-start gap-2',
        disabled ? 'cursor-not-allowed opacity-55' : 'cursor-pointer',
        className,
      )}
    >
      <span className="relative mt-px flex shrink-0">
        <input
          ref={inputRef}
          id={id}
          type="checkbox"
          name={name}
          checked={checked}
          disabled={disabled}
          onChange={handleChange}
          className="peer absolute inset-0 h-full w-full cursor-pointer opacity-0 disabled:cursor-not-allowed"
        />
        <span
          className={cn(
            'flex size-4 items-center justify-center rounded-[3px] border transition-colors duration-150',
            'peer-focus-visible:ring-2 peer-focus-visible:ring-ring peer-focus-visible:ring-offset-1',
            checked || isIndeterminate
              ? 'border-primary bg-primary text-primary-foreground'
              : 'border-border bg-background',
          )}
        >
          {isIndeterminate ? (
            <Minus size={10} strokeWidth={2.5} />
          ) : checked ? (
            <Check size={10} strokeWidth={2.5} />
          ) : null}
        </span>
      </span>
      {(label || description) && (
        <span className="flex flex-col gap-0.5">
          {label && <span className="text-[13px] leading-snug text-foreground">{label}</span>}
          {description && <span className="text-xs text-muted-foreground">{description}</span>}
        </span>
      )}
    </label>
  )
}
