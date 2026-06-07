'use client'
import { Button } from '@project/ui/components/ui/button'

interface Props {
  page: number
  totalPages: number
  onPageChange: (page: number) => void
}

export function Pagination({ page, totalPages, onPageChange }: Props) {
  if (totalPages <= 1) return null
  return (
    <div className="flex items-center gap-2 mt-4">
      {page > 1 && (
        <Button variant="outline" size="sm" onClick={() => onPageChange(page - 1)}>
          ← Prev
        </Button>
      )}
      <span className="text-sm text-muted-foreground">
        Page {page} of {totalPages}
      </span>
      {page < totalPages && (
        <Button variant="outline" size="sm" onClick={() => onPageChange(page + 1)}>
          Next →
        </Button>
      )}
    </div>
  )
}
