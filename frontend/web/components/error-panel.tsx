import { Button } from '@project/ui/components/ui/button'

// An error with a way to try again. The alert role makes a screen reader announce it.
export function ErrorPanel({
  title,
  message,
  onRetry,
}: {
  title: string
  message: string
  onRetry: () => void
}) {
  return (
    <div role="alert" className="flex flex-col items-center justify-center gap-4 py-20 text-center">
      <h2 className="text-xl font-semibold">{title}</h2>
      <p className="text-muted-foreground">{message}</p>
      <Button variant="outline" onClick={onRetry}>
        Try again
      </Button>
    </div>
  )
}
