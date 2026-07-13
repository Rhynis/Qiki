'use client'

import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { Button } from '@/components/ui/button'

type ProductPaginationProps = {
  page: number
  limit: number
  hasMore: boolean
}

export function ProductPagination({ page, limit, hasMore }: ProductPaginationProps) {
  const t = useTranslations('products')
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()

  function goToPage(nextPage: number) {
    const next = new URLSearchParams(searchParams.toString())
    next.set('skip', String((nextPage - 1) * limit))
    next.set('limit', String(limit))
    router.replace(`${pathname}?${next.toString()}`)
  }

  return (
    <div className="flex items-center justify-end gap-2">
      <Button variant="outline" disabled={page <= 1} onClick={() => goToPage(page - 1)}>
        <ChevronLeft className="mr-2 h-4 w-4" />
        {t('previous')}
      </Button>
      <Button variant="outline" disabled={!hasMore} onClick={() => goToPage(page + 1)}>
        {t('nextPage')}
        <ChevronRight className="ml-2 h-4 w-4" />
      </Button>
    </div>
  )
}
