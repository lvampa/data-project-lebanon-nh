'use client'
import { Suspense } from 'react'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { Pagination } from '@project/ui/components/data/pagination'

interface Props {
  page: number
  total: number
  perPage: number
}

function PageNavInner({ page, total, perPage }: Props) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const totalPages = Math.ceil(total / perPage)

  function goTo(next: number) {
    const params = new URLSearchParams(searchParams)
    params.set('page', String(next))
    router.push(`${pathname}?${params}`)
  }

  return <Pagination page={page} totalPages={totalPages} onPageChange={goTo} />
}

// useSearchParams needs a Suspense boundary, so it lives here once instead of in every page.
export function PageNav(props: Props) {
  return (
    <Suspense>
      <PageNavInner {...props} />
    </Suspense>
  )
}
