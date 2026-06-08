'use client'

import { useEffect } from 'react'
import { Button } from '@project/ui/components/ui/button'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error(error)
  }, [error])

  return (
    <div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
      <h2 className="text-xl font-semibold">Something went wrong</h2>
      <p className="text-sm text-muted-foreground">
        {error.digest ? `Error ID: ${error.digest}` : 'An unexpected error occurred.'}
      </p>
      <Button variant="outline" onClick={reset}>
        Try again
      </Button>
    </div>
  )
}
