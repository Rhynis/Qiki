'use client'

import { useMemo, useState } from 'react'
import Link from 'next/link'
import { useTranslations } from 'next-intl'
import { useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { ArrowLeft, Flame, Info } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { GasSafetyNotice } from '@/components/shop/gas-safety-notice'
import { PriceDisplay } from '@/components/shop/price-display'
import { StockBadge } from '@/components/shop/stock-badge'
import { WishlistButton } from '@/components/shop/wishlist-button'
import { useCartStore } from '@/lib/stores/cart-store'
import { formatPrice, formatProductSize } from '@/lib/utils/format'
import { effectivePrice } from '@/lib/utils/pricing'
import type { Product } from '@/types/product'

type ProductDetailProps = {
  product: Product
  variants?: Product[]
}

/** A short, customer-friendly label for a variant option (colour / size). */
function variantOptionLabel(variant: Product): string {
  if (variant.variant_label) return variant.variant_label
  const size = formatProductSize(variant.size_kg, variant.unit)
  return variant.colour ? `${size} (${variant.colour})` : size
}

export function ProductDetail({ product, variants }: ProductDetailProps) {
  const t = useTranslations('productDetail')
  const router = useRouter()
  const addItem = useCartStore((state) => state.addItem)

  // Offer a selector only for water with more than one variant to choose from.
  // Gas varies by size (6/12/45 kg); grouping it under a selector kept the page
  // title fixed to the originally loaded product while the selected size
  // changed underneath it, so gas never shows a selector — the detail page
  // always shows exactly the one product that was navigated to (#342).
  const options = useMemo(
    () => (product.category === 'nuoc_uong' && variants && variants.length > 1 ? variants : []),
    [product.category, variants]
  )
  const [selectedId, setSelectedId] = useState(product.id)
  const selected = useMemo(
    () => options.find((variant) => variant.id === selectedId) ?? product,
    [options, selectedId, product]
  )

  // Prefer the detailed (long) description on the product page, falling back to the
  // short listing description when no long text has been provided yet.
  const detailDescription =
    selected.long_description ??
    product.long_description ??
    selected.description ??
    product.description

  const inStock = selected.stock_quantity > 0
  const addToCart = () => {
    addItem(selected, 1)
    toast.success(t('addedToCart'))
  }

  return (
    <section className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <Button asChild variant="outline">
        <Link href="/products">
          <ArrowLeft className="mr-2 h-4 w-4" />
          {t('backToProducts')}
        </Link>
      </Button>

      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
        <div className="flex aspect-square items-center justify-center rounded-lg border bg-white">
          {(selected.image_url ?? product.image_url) ? (
            <div
              aria-label={product.name}
              className="h-full w-full rounded-lg bg-cover bg-center"
              style={{ backgroundImage: `url(${selected.image_url ?? product.image_url})` }}
            />
          ) : (
            <Flame className="h-20 w-20 text-primary" />
          )}
        </div>

        <div className="space-y-5">
          <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
              <StockBadge stockQuantity={selected.stock_quantity} />
              <Badge variant="outline">{product.brand}</Badge>
              <Badge variant="outline">{formatProductSize(selected.size_kg, selected.unit)}</Badge>
            </div>
            <h1 className="text-3xl font-semibold tracking-normal text-slate-950 md:text-4xl">
              {product.name}
            </h1>
            <PriceDisplay
              listPrice={selected.price}
              salePrice={selected.sale_price}
              priceClassName="text-3xl font-semibold text-primary"
            />
            <p className="text-sm text-slate-600">SKU {selected.sku}</p>
          </div>

          {options.length > 0 ? (
            <div className="space-y-2">
              <p className="text-sm font-semibold text-slate-950">{t('selectVariant')}</p>
              <div
                aria-label={t('selectVariantAria')}
                className="flex flex-wrap gap-2"
                role="radiogroup"
              >
                {options.map((variant) => {
                  const isSelected = variant.id === selected.id
                  const soldOut = variant.stock_quantity <= 0
                  return (
                    <button
                      key={variant.id}
                      type="button"
                      role="radio"
                      aria-checked={isSelected ? 'true' : 'false'}
                      onClick={() => setSelectedId(variant.id)}
                      className={cn(
                        'rounded-lg border px-3 py-2 text-sm transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
                        isSelected
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-input text-slate-700 hover:border-primary/50',
                        soldOut && 'opacity-60'
                      )}
                    >
                      <span className="block font-medium">{variantOptionLabel(variant)}</span>
                      <span className="block text-xs text-slate-500">
                        {formatPrice(effectivePrice(variant))}
                        {soldOut ? ' · tạm hết' : ''}
                      </span>
                    </button>
                  )
                })}
              </div>
            </div>
          ) : null}

          {(selected.pricing_note ?? product.pricing_note) ? (
            <div className="rounded-lg border border-primary/20 bg-primary/5 p-4 text-sm text-slate-700">
              <div className="flex gap-3">
                <Info className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                <div>
                  <p className="font-semibold text-slate-950">{t('surchargeNote')}</p>
                  <p className="mt-1 leading-6">{selected.pricing_note ?? product.pricing_note}</p>
                </div>
              </div>
            </div>
          ) : null}

          {detailDescription ? (
            <Card>
              <CardHeader>
                <CardTitle>{t('description')}</CardTitle>
              </CardHeader>
              <CardContent className="whitespace-pre-line text-slate-700">
                {detailDescription}
              </CardContent>
            </Card>
          ) : null}

          {selected.category === 'gas' ? <GasSafetyNotice /> : null}

          <div className="flex flex-wrap gap-3">
            <Button disabled={!inStock} onClick={addToCart}>
              {t('addToCart')}
            </Button>
            <Button
              disabled={!inStock}
              variant="outline"
              onClick={() => {
                addItem(selected, 1)
                router.push('/checkout')
              }}
            >
              {t('buyNow')}
            </Button>
            <WishlistButton productId={selected.id} withLabel />
          </div>
        </div>
      </div>
    </section>
  )
}
