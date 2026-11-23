import { cn } from '../../lib/utils'

// The chip after a topic that is not ready yet. `onBrand` is for the dark footer.
export function ComingSoon({
  onBrand = false,
  className,
}: {
  onBrand?: boolean
  className?: string
}) {
  return (
    <span
      className={cn(
        'whitespace-nowrap rounded-full border px-2 py-0.5 font-mono text-xs font-medium uppercase leading-none tracking-wide',
        onBrand
          ? 'border-brand-foreground/20 bg-brand-foreground/10 text-brand-foreground/80'
          : 'border-border bg-secondary text-muted-foreground',
        className,
      )}
    >
      Coming soon
    </span>
  )
}

// The desktop nav has room for the chips only from xl up. Below that the topic is muted, and
// a screen reader still hears that it is coming soon.
export function ComingSoonInNav() {
  return (
    <>
      <ComingSoon className="hidden xl:inline" />
      <span className="sr-only xl:hidden">Coming soon</span>
    </>
  )
}
