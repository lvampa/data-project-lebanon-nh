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
      title="Failed to load incidents"
      message="The incidents data could not be loaded. Please try again."
      onRetry={retry}
    />
  )
}
