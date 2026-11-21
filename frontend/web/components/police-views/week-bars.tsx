import type { WeekFlag } from '@/lib/police-views/findings'
import { weekNote, weekStart } from './weeks'

// A small bar per week, on a scale the caller shares across cards. A week missing logs, or
// still filling in, is striped instead of solid.
export function WeekBars({
  weeks,
  max,
  flags,
  since,
  noun,
}: {
  weeks: number[]
  max: number
  flags: WeekFlag[]
  since: string
  noun: string
}) {
  return (
    <div
      className="mt-2.5 mb-1.5 flex h-10 items-end gap-px"
      role="img"
      aria-label={`${noun} by week`}
    >
      {weeks.map((value, week) => (
        <div
          key={week}
          className={`min-w-0 flex-1 rounded-t-xs ${flags[week] ? 'week-incomplete' : ''}`}
          style={{
            height: `${(value / max) * 100}%`,
            backgroundColor: 'var(--chart-ink)',
          }}
          data-tip-title={`Week of ${weekStart(since, week)}`}
          data-tip={[`${value.toLocaleString('en-US')} ${noun}`, weekNote(flags[week])]
            .filter(Boolean)
            .join('\n')}
        />
      ))}
    </div>
  )
}
