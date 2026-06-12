'use client'

import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useDropdownOpen } from './product-dropdown-context'

const sortOptions = {
  'created_at:desc': 'Mới nhất',
  'price:asc': 'Giá tăng dần',
  'price:desc': 'Giá giảm dần',
  'name:asc': 'Tên A-Z',
  'name:desc': 'Tên Z-A',
}

export function ProductSort() {
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
      value={value in sortOptions ? value : 'created_at:desc'}
      onValueChange={updateSort}
      {...sortDropdown}
    >
      <SelectTrigger aria-label="Sắp xếp" className="w-[180px]">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {Object.entries(sortOptions).map(([optionValue, label]) => (
          <SelectItem key={optionValue} value={optionValue}>
            {label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
