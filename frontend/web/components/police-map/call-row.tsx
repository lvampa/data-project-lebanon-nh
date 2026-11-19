import { buttonVariants } from '@project/ui/components/ui/button'
import { OutcomeLabel, TypeLabel } from '@/components/police-map/labels'
import { callTiming, channelLabel, shortName } from '@/lib/police-map/call'
import { categoryOf } from '@/lib/police-map/categories'
import { clockOf, formatCallTime } from '@/lib/police-map/format'
import type { PlaceCall } from '@/lib/types'

// A call on one line, opening to the rest of its record.
export function CallRow({ call }: { call: PlaceCall }) {
  const kind = categoryOf(call.category)
  const steps = [
    ['Called', clockOf(call.reported_at)],
    ['Dispatched', clockOf(call.dispatched_at)],
    ['Arrived', clockOf(call.arrived_at)],
    ['Cleared', clockOf(call.cleared_at)],
  ].filter((step): step is [string, string] => step[1] !== null)
  const { arrivedAfter, onScene } = callTiming(call)
  const timing = [
    arrivedAfter === null
      ? null
      : arrivedAfter < 1
        ? 'Police arrived within a minute'
        : `Police arrived in ${arrivedAfter} min`,
    onScene === null ? null : `${onScene} min on scene`,
  ].filter((line) => line !== null)
  const officer = shortName(call.officer)
  const who = [officer && `Officer ${officer}`, `Case ${call.case_number}`].filter(Boolean)

  return (
    <li className="border-b border-border text-sm">
      <details className="group">
        <summary className="flex cursor-pointer list-none gap-2.5 py-2 marker:hidden">
          <span
            className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-sm"
            style={{ background: kind.color }}
            title={kind.label}
          />
          <time className="w-24 shrink-0 font-mono text-xs text-muted-foreground">
            {formatCallTime(call.reported_at)}
          </time>
          <span>
            <TypeLabel type={call.incident_type} />
            <small className="mt-px block text-xs text-muted-foreground">
              {channelLabel(call.call_source)} · <OutcomeLabel disposition={call.disposition} />
            </small>
          </span>
        </summary>
        <div className="pb-3 pl-6 text-xs text-muted-foreground">
          {steps.length > 1 && (
            <ol className="mb-2 flex gap-4">
              {steps.map(([label, time]) => (
                <li key={label}>
                  <span className="block">{label}</span>
                  <b className="font-mono font-medium text-foreground">{time}</b>
                </li>
              ))}
            </ol>
          )}
          {timing.length > 0 && <p className="mb-1">{timing.join(' · ')}</p>}
          <p>{who.join(' · ')}</p>
          <a
            href={call.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className={buttonVariants({ variant: 'link', size: 'xs' })}
          >
            View in the city&apos;s log
          </a>
        </div>
      </details>
    </li>
  )
}
