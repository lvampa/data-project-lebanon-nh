'use client'
import { Button } from '@project/ui/components/ui/button'
import type { DataState } from '@/components/use-data-file'

// What a page shows until all of its files are ready.
export function DataStatus({ states }: { states: DataState<unknown>[] }) {
  const failed = states.find(
    (state): state is Extract<DataState<unknown>, { status: 'error' }> => state.status === 'error',
  )
  if (failed) {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-20 text-center">
        <h2 className="text-xl font-semibold">The data did not load</h2>
        <p className="text-muted-foreground">Check your connection and try again.</p>
        <Button variant="outline" onClick={failed.retry}>
          Try again
        </Button>
      </div>
    )
  }
  return (
    <p role="status" className="py-20 text-center text-sm text-muted-foreground">
      Loading the data…
    </p>
  )
}
