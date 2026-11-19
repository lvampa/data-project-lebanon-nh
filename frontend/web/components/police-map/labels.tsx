import { plainOutcome, plainType } from '@/lib/police-map/labels'

const HOVER_WORDS =
  'cursor-help underline decoration-muted-foreground/60 decoration-dotted underline-offset-4'

// The log's own words show on hover, and are read out after the plain label, so a reader
// can check a plain label against the record without a mouse.
function Labelled({ label, original, title }: { label: string; original: string; title: string }) {
  return (
    <abbr title={title} className={HOVER_WORDS}>
      {label}
      {label !== original && <span className="sr-only"> (logged as {original})</span>}
    </abbr>
  )
}

export function TypeLabel({ type }: { type: string | null }) {
  if (!type) return <>{plainType(type)}</>
  return <Labelled label={plainType(type)} original={type} title={type} />
}

export function OutcomeLabel({ disposition }: { disposition: string | null }) {
  const { label, hint } = plainOutcome(disposition)
  if (!disposition) return <>{label}</>
  const title = hint ? `${hint} (logged as "${disposition}")` : disposition
  return <Labelled label={label} original={disposition} title={title} />
}
