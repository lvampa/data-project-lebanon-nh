'use client'
import { OperaHouseLoader } from '@project/ui/components/site/opera-house-loader'
import { ErrorPanel } from '@/components/error-panel'
import type { DataState } from '@/components/use-data-file'

// What a page shows until all of its files are ready.
export function DataStatus({ states }: { states: DataState<unknown>[] }) {
  const failed = states.filter(
    (state): state is Extract<DataState<unknown>, { status: 'error' }> => state.status === 'error',
  )
  if (failed.length > 0) {
    return (
      <ErrorPanel
        title="The data did not load"
        message="Check your connection and try again."
        onRetry={() => failed.forEach((state) => state.retry())}
      />
    )
  }
  return (
    <div className="flex justify-center py-20">
      <OperaHouseLoader size={80} label="Loading the data" />
    </div>
  )
}
