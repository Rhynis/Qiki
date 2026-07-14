'use client'

import { Search } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useProductBrands } from '@/lib/hooks/use-products'
import type { ProductCategory } from '@/types/product'
import { useDropdownOpen } from './product-dropdown-context'

const sizes = ['6', '12', '45']

type ProductFiltersProps = {
  category?: ProductCategory
}

export function ProductFilters({ category }: ProductFiltersProps) {
  const t = useTranslations('products')
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const [search, setSearch] = useState(searchParams.get('search') ?? '')
  const [type, setType] = useState<string>(category ?? 'all')
  const [brand, setBrand] = useState(searchParams.get('brand') ?? 'all')
  const [size, setSize] = useState(searchParams.get('size_kg') ?? 'all')
  const [inStockOnly, setInStockOnly] = useState(searchParams.get('in_stock_only') === 'true')
  const { data: brands = [] } = useProductBrands(category)
  // Single-open: only one of these dropdowns is open at a time (shared context).
  const typeDropdown = useDropdownOpen('type')
  const brandDropdown = useDropdownOpen('brand')
  const sizeDropdown = useDropdownOpen('size')

  function changeType(nextType: string) {
    setType(nextType)
    const next = new URLSearchParams(searchParams.toString())
    if (nextType === 'all') {
      next.delete('category')
    } else {
      next.set('category', nextType)
    }
    // Size (kg) only applies to gas — drop it when switching catalog scope.
    next.delete('size_kg')
    next.delete('skip')
    router.replace(`${pathname}?${next.toString()}`)
  }

  function applyFilters() {
    const next = new URLSearchParams()
    if (category) next.set('category', category)
    if (search.trim()) next.set('search', search.trim())
    if (brand !== 'all') next.set('brand', brand)
    if (category !== 'nuoc_uong' && size !== 'all') next.set('size_kg', size)
    if (inStockOnly) next.set('in_stock_only', 'true')
    // Sorting is managed by <ProductSort/> via the URL — preserve it when applying filters.
    const sortBy = searchParams.get('sort_by')
    const sortOrder = searchParams.get('sort_order')
    if (sortBy) next.set('sort_by', sortBy)
    if (sortOrder) next.set('sort_order', sortOrder)
    router.replace(`${pathname}?${next.toString()}`)
  }

  function clearFilters() {
    setSearch('')
    setBrand('all')
    setSize('all')
    setInStockOnly(false)
    router.replace(category ? `${pathname}?category=${category}` : pathname)
  }

  // "Loại" (category) on the general /products page; "Kích thước" only on the gas page.
  const showTypeFilter = !category
  const showSizeFilter = category === 'gas'
  const brandOptions = brand !== 'all' && !brands.includes(brand) ? [brand, ...brands] : brands

  return (
    <div className="rounded-lg border bg-white p-4">
      <div
        className={
          showTypeFilter || showSizeFilter
            ? 'grid gap-4 lg:grid-cols-[1.2fr_1fr_160px]'
            : 'grid gap-4 lg:grid-cols-[1.2fr_1fr]'
        }
      >
        <div className="space-y-2">
          <Label htmlFor="search">{t('search')}</Label>
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
            <Input
              id="search"
              className="pl-9"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') applyFilters()
              }}
            />
          </div>
        </div>
        <div className="space-y-2">
          <Label>{t('brand')}</Label>
          <Select modal={false} value={brand} onValueChange={setBrand} {...brandDropdown}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('all')}</SelectItem>
              {brandOptions.map((item) => (
                <SelectItem key={item} value={item}>
                  {item}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {showTypeFilter ? (
          <div className="space-y-2">
            <Label>{t('type')}</Label>
            <Select modal={false} value={type} onValueChange={changeType} {...typeDropdown}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('all')}</SelectItem>
                <SelectItem value="gas">{t('categoryGas')}</SelectItem>
                <SelectItem value="nuoc_uong">{t('categoryWater')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        ) : null}
        {showSizeFilter ? (
          <div className="space-y-2">
            <Label>{t('size')}</Label>
            <Select modal={false} value={size} onValueChange={setSize} {...sizeDropdown}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('all')}</SelectItem>
                {sizes.map((item) => (
                  <SelectItem key={item} value={item}>
                    {t('sizeKg', { size: item })}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ) : null}
      </div>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <label className="flex items-center gap-2 text-sm">
          <Checkbox
            checked={inStockOnly}
            onCheckedChange={(value) => setInStockOnly(value === true)}
          />
          {t('inStockOnly')}
        </label>
        <div className="flex gap-2">
          <Button type="button" variant="outline" onClick={clearFilters}>
            {t('clearFilters')}
          </Button>
          <Button type="button" onClick={applyFilters}>
            {t('applyFilters')}
          </Button>
        </div>
      </div>
    </div>
  )
}
