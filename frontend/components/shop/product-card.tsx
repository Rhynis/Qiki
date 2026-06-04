import Link from 'next/link'
import { Flame } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatPrice } from '@/lib/utils/format'
import { StockBadge } from '@/components/shop/stock-badge'
import type { Product } from '@/types/product'

type ProductCardProps = {
  product: Product
}

export function ProductCard({ product }: ProductCardProps) {
  return (
    <Card className="flex h-full flex-col overflow-hidden">
      <div className="flex aspect-[4/3] items-center justify-center bg-slate-100">
        {product.image_url ? (
          <div
            aria-label={product.name}
            className="h-full w-full bg-cover bg-center"
            style={{ backgroundImage: `url(${product.image_url})` }}
          />
        ) : (
          <Flame className="h-12 w-12 text-primary" />
        )}
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
          <Badge variant="outline">{Number(product.size_kg).toLocaleString('vi-VN')}kg</Badge>
          <Badge variant="outline">SKU {product.sku}</Badge>
        </div>
      </CardHeader>
      <CardContent className="flex-1 space-y-3">
        <p className="text-2xl font-semibold text-primary">{formatPrice(product.price)}</p>
        {product.description ? (
          <p className="line-clamp-2 text-sm text-slate-600">{product.description}</p>
        ) : null}
      </CardContent>
      <div className="p-6 pt-0">
        <Button asChild className="w-full">
          <Link href={`/products/${product.id}`}>Xem chi tiết</Link>
        </Button>
      </div>
    </Card>
  )
}
