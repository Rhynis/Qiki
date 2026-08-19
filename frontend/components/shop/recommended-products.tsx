'use client'

import { useTranslations } from 'next-intl'
import { ProductCard } from '@/components/shop/product-card'
import { Skeleton } from '@/components/ui/skeleton'
import { useRecommendedProducts } from '@/lib/hooks/use-recommendations'

type RecommendedProductsProps = {
  productId: string
}

/** "Gợi ý cho bạn" row on the product detail page: ranked suggestions with a
 * short, catalog-derived reason under each card (not fabricated). */
export function RecommendedProducts({ productId }: RecommendedProductsProps) {
  const t = useTranslations('recommendations')
  const { data, isLoading } = useRecommendedProducts(productId)

  if (isLoading) {
    return (
      <section className="space-y-4">
        <Skeleton className="h-7 w-40" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-80 w-full" />
          ))}
        </div>
      </section>
    )
  }

  if (!data || data.length === 0) return null

  return (
    <section className="space-y-4">
      <h2 className="text-2xl font-semibold">{t('title')}</h2>
      {/* items-start: ProductCard uses h-full to equalize height within its
          own grid (product-grid.tsx); without items-start here, CSS Grid's
          default row-stretch makes h-full resolve against the (taller) row
          instead of this cell's own content, pushing the reason text below
          into the next row instead of directly under its card. */}
      <div className="grid items-start gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {data.map((product) => (
          <div key={product.id} className="space-y-2">
            <ProductCard product={product} />
            <p className="text-sm text-primary">{product.reason}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
