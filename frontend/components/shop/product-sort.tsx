'use client'

import { useTranslations } from 'next-intl'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useDropdownOpen } from './product-dropdown-context'

const sortOptionKeys = {
  'created_at:desc': 'sortNewest',
  'price:asc': 'sortPriceAsc',
  'price:desc': 'sortPriceDesc',
  'name:asc': 'sortNameAsc',
  'name:desc': 'sortNameDesc',
} as const

export function ProductSort() {
  const t = useTranslations('products')
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const value = `${searchParams.get('sort_by') ?? 'created_at'}:${searchParams.get('sort_order') ?? 'desc'}`
  const sortDropdown = useDropdownOpen('sort')

  function updateSort(nextValue: string) {
    const [sortBy, sortOrder] = nextValue.split(':')
    const next = new URLSearchParams(searchParams.toString())
    if (sortBy) next.set('sort_by', sortBy)
    if (sortOrder) next.set('sort_order', sortOrder)
    next.delete('skip')
    router.replace(`${pathname}?${next.toString()}`)
  }

  return (
    <Select
      modal={false}
      value={value in sortOptionKeys ? value : 'created_at:desc'}
      onValueChange={updateSort}
      {...sortDropdown}
    >
      <SelectTrigger aria-label={t('sort')} className="w-[180px]">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {Object.entries(sortOptionKeys).map(([optionValue, labelKey]) => (
          <SelectItem key={optionValue} value={optionValue}>
            {t(labelKey)}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
