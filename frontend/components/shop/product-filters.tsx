'use client'

import { Search } from 'lucide-react'
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

const sizes = ['6', '12', '45']

type ProductFiltersProps = {
  category?: ProductCategory
}

export function ProductFilters({ category }: ProductFiltersProps) {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const [search, setSearch] = useState(searchParams.get('search') ?? '')
  const [brand, setBrand] = useState(searchParams.get('brand') ?? 'all')
  const [size, setSize] = useState(searchParams.get('size_kg') ?? 'all')
  const [inStockOnly, setInStockOnly] = useState(searchParams.get('in_stock_only') === 'true')
  const { data: brands = [] } = useProductBrands(category)

  function applyFilters() {
    const next = new URLSearchParams()
    if (category) next.set('category', category)
    if (search.trim()) next.set('search', search.trim())
    if (brand !== 'all') next.set('brand', brand)
    if (category !== 'nuoc_uong' && size !== 'all') next.set('size_kg', size)
    if (inStockOnly) next.set('in_stock_only', 'true')
    // Sắp xếp do <ProductSort/> quản qua URL — giữ lại khi áp dụng bộ lọc.
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

  const showSizeFilter = category !== 'nuoc_uong'
  const brandOptions = brand !== 'all' && !brands.includes(brand) ? [brand, ...brands] : brands

  return (
    <div className="rounded-lg border bg-white p-4">
      <div
        className={
          showSizeFilter
            ? 'grid gap-4 lg:grid-cols-[1.2fr_1fr_160px]'
            : 'grid gap-4 lg:grid-cols-[1.2fr_1fr]'
        }
      >
        <div className="space-y-2">
          <Label htmlFor="search">Tìm kiếm</Label>
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
          <Label>Thương hiệu</Label>
          <Select modal={false} value={brand} onValueChange={setBrand}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tất cả</SelectItem>
              {brandOptions.map((item) => (
                <SelectItem key={item} value={item}>
                  {item}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {showSizeFilter ? (
          <div className="space-y-2">
            <Label>Kích thước</Label>
            <Select modal={false} value={size} onValueChange={setSize}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tất cả</SelectItem>
                {sizes.map((item) => (
                  <SelectItem key={item} value={item}>
                    {item} kg
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
          Chỉ hiện sản phẩm còn hàng
        </label>
        <div className="flex gap-2">
          <Button type="button" variant="outline" onClick={clearFilters}>
            Xóa lọc
          </Button>
          <Button type="button" onClick={applyFilters}>
            Áp dụng
          </Button>
        </div>
      </div>
    </div>
  )
}
