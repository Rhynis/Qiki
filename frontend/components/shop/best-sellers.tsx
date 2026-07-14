'use client'

import { useQuery } from '@tanstack/react-query'
import { ProductGrid } from '@/components/shop/product-grid'
import { getBestSellers } from '@/lib/api/orders'

export function BestSellers() {
  const { data } = useQuery({
    queryKey: ['best-sellers', 8],
    queryFn: () => getBestSellers(8),
  })

  if (!data || data.length === 0) return null

  return (
    <section className="mx-auto max-w-6xl space-y-4 px-4 py-10">
      <div className="space-y-1">
        <h2 className="text-2xl font-semibold">Bán chạy</h2>
        <p className="text-sm text-slate-600">Những sản phẩm được khách đặt nhiều nhất.</p>
      </div>
      <ProductGrid products={data} />
    </section>
  )
}
