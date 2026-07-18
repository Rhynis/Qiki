'use client'

import Link from 'next/link'
import { useState } from 'react'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { validateCoupon } from '@/lib/api/coupons'
import { calculateCartShipping, useCartStore } from '@/lib/stores/cart-store'
import { useCheckoutStore } from '@/lib/stores/checkout-store'
import { formatPrice } from '@/lib/utils/format'

export function OrderSummarySidebar() {
  const t = useTranslations('cart')
  const items = useCartStore((state) => state.items)
  const subtotal = useCartStore((state) => state.getTotal())
  // Shipping is display-only and mirrors the server; an empty cart is always 0đ.
  const shippingFee = calculateCartShipping(items)

  const couponCode = useCheckoutStore((state) => state.couponCode)
  const discountAmount = useCheckoutStore((state) => state.discountAmount)
  const setCoupon = useCheckoutStore((state) => state.setCoupon)
  const clearCoupon = useCheckoutStore((state) => state.clearCoupon)

  const [codeInput, setCodeInput] = useState('')
  const [couponError, setCouponError] = useState<string | null>(null)
  const [isValidating, setIsValidating] = useState(false)

  // The server recomputes the authoritative discount at checkout; this is display-only.
  const discount = couponCode ? Math.min(discountAmount, subtotal) : 0
  const total = Math.max(0, subtotal + shippingFee - discount)

  const applyCoupon = async () => {
    const code = codeInput.trim()
    if (!code) return
    setCouponError(null)
    setIsValidating(true)
    try {
      const result = await validateCoupon(code, subtotal)
      setCoupon(result.code, Number(result.discount_amount))
      setCodeInput('')
    } catch (caught) {
      clearCoupon()
      setCouponError(caught instanceof Error ? caught.message : 'Mã giảm giá không hợp lệ')
    } finally {
      setIsValidating(false)
    }
  }

  const removeCoupon = () => {
    clearCoupon()
    setCouponError(null)
  }

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
      {items.length > 0 ? (
        <>
          <Separator />
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="coupon-code">
              Mã giảm giá
            </label>
            {couponCode ? (
              <div className="flex items-center justify-between gap-2 text-sm">
                <span className="font-medium text-emerald-700">
                  {t('couponApplied', { code: couponCode })}
                </span>
                <button
                  type="button"
                  className="text-slate-500 hover:text-primary hover:underline"
                  onClick={removeCoupon}
                >
                  Bỏ mã
                </button>
              </div>
            ) : (
              <div className="flex gap-2">
                <input
                  id="coupon-code"
                  value={codeInput}
                  onChange={(event) => setCodeInput(event.target.value)}
                  placeholder="Nhập mã"
                  className="h-9 w-full rounded-md border px-3 text-sm uppercase outline-none focus:ring-2 focus:ring-ring"
                />
                <Button
                  type="button"
                  variant="outline"
                  disabled={isValidating || !codeInput.trim()}
                  onClick={() => void applyCoupon()}
                >
                  {isValidating ? '...' : 'Áp dụng'}
                </Button>
              </div>
            )}
            {couponError ? <p className="text-sm text-red-600">{couponError}</p> : null}
          </div>
        </>
      ) : null}
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
        {discount > 0 ? (
          <div className="flex justify-between text-emerald-700">
            <span>{t('discount')}</span>
            <span>-{formatPrice(discount)}</span>
          </div>
        ) : null}
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
