import Link from 'next/link'
import { Flame } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatPrice, formatProductSize } from '@/lib/utils/format'
import { StockBadge } from '@/components/shop/stock-badge'
import { WishlistButton } from '@/components/shop/wishlist-button'
import type { Product } from '@/types/product'

type ProductCardProps = {
  product: Product
}

export function ProductCard({ product }: ProductCardProps) {
  const productHref = `/products/${product.id}`

  return (
    <Card className="group relative flex h-full cursor-pointer flex-col overflow-hidden transition-shadow hover:shadow-md">
      <Link
        aria-label={`Xem chi tiết ${product.name}`}
        className="absolute inset-0 z-10 rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        href={productHref}
      >
        <span className="sr-only">Xem chi tiết {product.name}</span>
      </Link>
      <div className="relative flex aspect-[4/3] items-center justify-center bg-slate-100">
        {product.image_url ? (
          <div
            aria-label={product.name}
            className="h-full w-full bg-cover bg-center"
            style={{ backgroundImage: `url(${product.image_url})` }}
          />
        ) : (
          <Flame className="h-12 w-12 text-primary" />
        )}
        <WishlistButton
          productId={product.id}
          className="absolute right-2 top-2 z-20 bg-white/80 hover:bg-white"
        />
      </div>
      <CardHeader className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-sm text-slate-600">{product.brand}</p>
            <CardTitle className="line-clamp-2 min-h-[3.5rem] text-xl leading-7">
              {product.name}
            </CardTitle>
          </div>
          <StockBadge stockQuantity={product.stock_quantity} />
        </div>
        <div className="flex flex-wrap gap-2 text-sm">
          <Badge variant="outline">{formatProductSize(product.size_kg, product.unit)}</Badge>
          <Badge variant="outline">SKU {product.sku}</Badge>
        </div>
      </CardHeader>
      <CardContent className="flex-1 space-y-3">
        <p className="text-2xl font-semibold text-primary">{formatPrice(product.price)}</p>
        {product.description ? (
          <p className="line-clamp-2 text-sm text-slate-600">{product.description}</p>
        ) : null}
      </CardContent>
      <div className="relative z-20 p-6 pt-0">
        <Button asChild className="w-full">
          <Link href={productHref}>Xem chi tiết</Link>
        </Button>
      </div>
    </Card>
  )
}
