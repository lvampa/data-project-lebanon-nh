'use client'

import { useEffect } from 'react'
import { Button } from '@project/ui/components/ui/button'

export default function Error({
  error,
  retry,
}: {
  error: Error & { digest?: string }
  retry: () => void
}) {
  useEffect(() => {
    // eslint-disable-next-line no-console -- An error page is the only record of the error it caught.
    console.error(error)
  }, [error])

  return (
    <div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
      <h2 className="text-xl font-semibold">Failed to load incidents</h2>
      <p className="text-muted-foreground">
        The incidents data could not be loaded. Please try again.
      </p>
      <Button variant="outline" onClick={() => retry()}>
        Try again
      </Button>
    </div>
  )
}
