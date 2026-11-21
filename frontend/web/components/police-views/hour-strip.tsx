import { clock } from '@/lib/police-views/findings'

// Three steps, each 3:1 on the card, darkest for the busiest hours. An hour with nothing is
// the track color, so the strip never fades below what a reader can see.
function stepOf(value: number, max: number): string {
  if (value === 0) return 'var(--secondary)'
  return `var(--step-${Math.min(3, Math.floor((value / max) * 3) + 1)})`
}

const LABELS = ['12am', '6am', '12pm', '6pm', '11pm']

// Activity by hour of the day, midnight to midnight.
export function HourStrip({ hours, compact = false }: { hours: number[]; compact?: boolean }) {
  const max = Math.max(1, ...hours)
  return (
    <div>
      <div className="grid grid-cols-24 gap-0.5" role="img" aria-label="Activity by hour of day">
        {hours.map((value, hour) => (
          <div
            key={hour}
            className={compact ? 'h-2 rounded-xs' : 'h-6 rounded-xs'}
            style={{ background: stepOf(value, max) }}
            data-tip-title={`${clock(hour)} to ${clock(hour + 1)}`}
            data-tip={value.toLocaleString('en-US')}
          />
        ))}
      </div>
      {!compact && (
        <div className="mt-1 flex justify-between text-xs text-muted-foreground">
          {LABELS.map((label) => (
            <span key={label}>{label}</span>
          ))}
        </div>
      )}
    </div>
  )
}
