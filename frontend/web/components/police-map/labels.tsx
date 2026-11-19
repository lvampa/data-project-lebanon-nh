import { plainOutcome, plainType } from '@/lib/police-map/labels'

// The log's own words show on hover, so a reader can check a plain label against the record.
export function TypeLabel({ type }: { type: string | null }) {
  return (
    <abbr
      title={type ?? ''}
      className="cursor-help underline decoration-muted-foreground/60 decoration-dotted underline-offset-4"
    >
      {plainType(type)}
    </abbr>
  )
}

export function OutcomeLabel({ disposition }: { disposition: string | null }) {
  const { label, hint } = plainOutcome(disposition)
  if (!disposition) return <>{label}</>
  return (
    <abbr
      title={hint ? `${hint} (logged as "${disposition}")` : disposition}
      className="cursor-help underline decoration-muted-foreground/60 decoration-dotted underline-offset-4"
    >
      {label}
    </abbr>
  )
}
