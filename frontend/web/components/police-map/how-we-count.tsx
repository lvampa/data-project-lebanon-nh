import { sinceLabel } from '@/lib/police-map/format'

export function HowWeCount({ since }: { since: string }) {
  return (
    <details className="mt-5 border-t border-border pt-3 text-sm">
      <summary className="cursor-pointer font-medium text-primary">About these numbers</summary>
      <p className="mt-2">
        Each entry in the city&apos;s daily police log is counted at the place it names. Entries
        include calls from the public and the patrols, checks and stops officers start themselves.
        Traffic counts toward the street, even when the log names a nearby business. Data runs from{' '}
        {sinceLabel(since)}.
      </p>
      <p className="mt-2 text-muted-foreground">
        An entry shows where police went and why. It doesn&apos;t say who was at fault.
      </p>
    </details>
  )
}
