'use client'

import { useEffect } from 'react'
import { ErrorPanel } from '@/components/error-panel'

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
    <ErrorPanel
      title="Something went wrong"
      message="An unexpected error occurred. Please try again."
      onRetry={retry}
    />
  )
}
