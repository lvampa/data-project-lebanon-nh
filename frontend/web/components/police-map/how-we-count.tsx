import { sinceLabel } from '@/lib/police-map/format'

export function HowWeCount({ since }: { since: string }) {
  return (
    <details className="mt-5 border-t border-border pt-3 text-sm">
      <summary className="cursor-pointer font-medium text-primary">About these numbers</summary>
      <p className="mt-2">
        Each call is counted at the place the police log names. Traffic calls count toward the
        street, even when the log names a nearby business. Data runs from {sinceLabel(since)}, and
        comes from the city&apos;s daily police logs.
      </p>
      <p className="mt-2 text-muted-foreground">
        A call shows where police went and why. It doesn&apos;t say who was at fault.
      </p>
    </details>
  )
}
