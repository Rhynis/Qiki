'use client'

import Link from 'next/link'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { calculateCartShipping, useCartStore } from '@/lib/stores/cart-store'
import { formatPrice } from '@/lib/utils/format'

export function OrderSummarySidebar() {
  const t = useTranslations('cart')
  const items = useCartStore((state) => state.items)
  const subtotal = useCartStore((state) => state.getTotal())
  // Shipping is display-only and mirrors the server; an empty cart is always 0đ.
  const shippingFee = calculateCartShipping(items)
  const total = subtotal + shippingFee

  return (
    <aside className="sticky top-6 space-y-4 rounded-lg border bg-white p-4">
      <div>
        <h2 className="text-base font-semibold">{t('summaryTitle')}</h2>
        <p className="text-sm text-slate-600">{t('itemCount', { count: items.length })}</p>
      </div>
      <div className="space-y-3">
        {items.map((item) => (
          <div key={item.productId} className="flex justify-between gap-3 text-sm">
            <div className="min-w-0">
              <p className="truncate font-medium">{item.name}</p>
              <p className="text-slate-600">x{item.quantity}</p>
            </div>
            <span className="shrink-0">{formatPrice(item.price * item.quantity)}</span>
          </div>
        ))}
      </div>
      <Separator />
      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span>{t('subtotal')}</span>
          <span>{formatPrice(subtotal)}</span>
        </div>
        <div className="flex justify-between">
          <span>{t('shippingFee')}</span>
          <span>{formatPrice(shippingFee)}</span>
        </div>
        <div className="flex justify-between text-base font-semibold">
          <span>{t('total')}</span>
          <span>{formatPrice(total)}</span>
        </div>
      </div>
      {items.length === 0 ? (
        <Button asChild className="w-full" variant="outline">
          <Link href="/products">{t('pickProducts')}</Link>
        </Button>
      ) : null}
    </aside>
  )
}
