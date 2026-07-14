'use client'

import { Flame, Heart, ShoppingBag, Trash2 } from 'lucide-react'
import { useTranslations } from 'next-intl'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { PageHeader } from '@/components/shared/page-header'
import { StockBadge } from '@/components/shop/stock-badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useAuth } from '@/lib/hooks/use-auth'
import { useToggleWishlist, useWishlist } from '@/lib/hooks/use-wishlist'
import { useCartStore } from '@/lib/stores/cart-store'
import { formatPrice, formatProductSize } from '@/lib/utils/format'

export default function WishlistPage() {
  const t = useTranslations('wishlist')
  const tProduct = useTranslations('products')
  const tButton = useTranslations('wishlistButton')
  const router = useRouter()
  const { user, isLoading, refreshUser } = useAuth()
  const [checked, setChecked] = useState(false)
  const { products, isLoading: wishlistLoading } = useWishlist()
  const toggle = useToggleWishlist()
  const addItem = useCartStore((state) => state.addItem)

  useEffect(() => {
    let mounted = true
    refreshUser()
      .then((currentUser) => {
        if (!currentUser) router.replace('/login?redirectTo=/wishlist')
      })
      .finally(() => {
        if (mounted) setChecked(true)
      })
    return () => {
      mounted = false
    }
  }, [refreshUser, router])

  if (!checked || isLoading) {
    return (
      <section className="mx-auto max-w-6xl space-y-4 px-4 py-8">
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
      </section>
    )
  }

  if (!user) return null

  return (
    <section className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <PageHeader title={t('title')} description={t('description')} />

      {wishlistLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </div>
      ) : products.length === 0 ? (
        <div className="rounded-lg border bg-white p-10 text-center">
          <Heart className="mx-auto h-8 w-8 text-slate-300" />
          <p className="mt-3 text-sm text-slate-600">{t('empty')}</p>
          <Button asChild className="mt-4" variant="outline">
            <Link href="/products">
              <ShoppingBag className="mr-2 h-4 w-4" />
              {t('explore')}
            </Link>
          </Button>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {products.map((product) => {
            const inStock = product.stock_quantity > 0
            return (
              <Card key={product.id} className="flex h-full flex-col overflow-hidden">
                <Link
                  href={`/products/${product.id}`}
                  className="flex aspect-[4/3] items-center justify-center bg-slate-100"
                  aria-label={tProduct('viewDetailsAria', { name: product.name })}
                >
                  {product.image_url ? (
                    <div
                      aria-hidden="true"
                      className="h-full w-full bg-cover bg-center"
                      style={{ backgroundImage: `url(${product.image_url})` }}
                    />
                  ) : (
                    <Flame className="h-10 w-10 text-primary" />
                  )}
                </Link>
                <CardContent className="flex flex-1 flex-col gap-3 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm text-slate-600">{product.brand}</p>
                      <Link
                        href={`/products/${product.id}`}
                        className="line-clamp-2 font-medium text-slate-900 hover:text-primary"
                      >
                        {product.name}
                      </Link>
                    </div>
                    <StockBadge stockQuantity={product.stock_quantity} />
                  </div>
                  <p className="text-lg font-semibold text-primary">{formatPrice(product.price)}</p>
                  <p className="text-xs text-slate-500">
                    {formatProductSize(product.size_kg, product.unit)}
                  </p>
                  <div className="mt-auto flex gap-2">
                    <Button
                      className="flex-1"
                      disabled={!inStock}
                      onClick={() => {
                        addItem(product, 1)
                        toast.success(t('addedToCart'))
                      }}
                    >
                      <ShoppingBag className="mr-2 h-4 w-4" />
                      {t('addToCart')}
                    </Button>
                    <Button
                      variant="outline"
                      size="icon"
                      title={tButton('remove')}
                      aria-label={tButton('remove')}
                      disabled={toggle.isPending}
                      onClick={() => toggle.mutate({ productId: product.id, saved: true })}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </section>
  )
}
