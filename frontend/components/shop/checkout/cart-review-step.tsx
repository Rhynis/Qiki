'use client'

import Link from 'next/link'
import { Minus, Plus, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useCartStore } from '@/lib/stores/cart-store'
import { formatPrice, formatProductSize } from '@/lib/utils/format'

export function CartReviewStep({ onNext }: { onNext: () => void }) {
  const items = useCartStore((state) => state.items)
  const updateQuantity = useCartStore((state) => state.updateQuantity)
  const removeItem = useCartStore((state) => state.removeItem)

  if (items.length === 0) {
    return (
      <div className="space-y-4 rounded-lg border bg-white p-6 text-center">
        <h2 className="text-xl font-semibold">Giỏ hàng đang trống</h2>
        <Button asChild>
          <Link href="/products">Xem sản phẩm</Link>
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border bg-white">
        {items.map((item) => (
          <div key={item.productId} className="flex gap-4 border-b p-4 last:border-b-0">
            <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-md bg-slate-100 text-sm text-slate-500">
              {item.imageUrl ? (
                <div
                  aria-label={item.name}
                  className="h-full w-full rounded-md bg-cover bg-center"
                  style={{ backgroundImage: `url(${item.imageUrl})` }}
                />
              ) : (
                formatProductSize(item.sizeKg, item.unit ?? 'kg')
              )}
            </div>
            <div className="min-w-0 flex-1 space-y-2">
              <div className="flex justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="truncate font-medium">{item.name}</h2>
                  <p className="text-sm text-slate-600">{item.brand}</p>
                </div>
                <p className="shrink-0 font-semibold">{formatPrice(item.price * item.quantity)}</p>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center rounded-md border">
                  <Button
                    aria-label="Giảm số lượng"
                    size="icon"
                    type="button"
                    variant="ghost"
                    onClick={() => updateQuantity(item.productId, item.quantity - 1)}
                  >
                    <Minus className="h-4 w-4" />
                  </Button>
                  <span className="w-10 text-center text-sm">{item.quantity}</span>
                  <Button
                    aria-label="Tăng số lượng"
                    size="icon"
                    type="button"
                    variant="ghost"
                    onClick={() => updateQuantity(item.productId, item.quantity + 1)}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>
                <Button
                  aria-label="Xóa sản phẩm"
                  size="icon"
                  type="button"
                  variant="ghost"
                  onClick={() => removeItem(item.productId)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="flex justify-end">
        <Button onClick={onNext}>Tiến hành thanh toán</Button>
      </div>
    </div>
  )
}
