import { useTranslations } from 'next-intl'
import { EmptyState } from '@/components/shared/empty-state'
import { ProductCard } from '@/components/shop/product-card'
import type { Product } from '@/types/product'

type ProductGridProps = {
  products: Product[]
}

export function ProductGrid({ products }: ProductGridProps) {
  const t = useTranslations('products')

  if (products.length === 0) {
    return <EmptyState title={t('emptyTitle')} description={t('emptyDescription')} />
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {products.map((product) => (
        <ProductCard key={product.id} product={product} />
      ))}
    </div>
  )
}
