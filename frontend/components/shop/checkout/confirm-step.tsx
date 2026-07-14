'use client'

import { useRef } from 'react'
import { useRouter } from 'next/navigation'
import { v4 as uuidv4 } from 'uuid'
import { toast } from 'sonner'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { useCreateOrder } from '@/lib/hooks/use-orders'
import { useCartStore } from '@/lib/stores/cart-store'
import { useCheckoutStore } from '@/lib/stores/checkout-store'
import { formatPhone, formatPrice } from '@/lib/utils/format'
import type { CheckoutRequest } from '@/types/order'
import { getDeliveryZoneByWard } from '@/utils/vietnamese-address'

function optionalText(value: string) {
  const trimmed = value.trim()
  return trimmed.length > 0 ? trimmed : null
}

export function ConfirmStep() {
  const router = useRouter()
  const idempotencyKey = useRef<string | null>(null)
  const items = useCartStore((state) => state.items)
  const clearCart = useCartStore((state) => state.clearCart)
  const form = useCheckoutStore((state) => state.form)
  const couponCode = useCheckoutStore((state) => state.couponCode)
  const previousStep = useCheckoutStore((state) => state.previousStep)
  const setLastOrder = useCheckoutStore((state) => state.setLastOrder)
  const resetCheckout = useCheckoutStore((state) => state.resetCheckout)
  const createOrder = useCreateOrder()
  const subtotal = items.reduce((sum, item) => sum + item.price * item.quantity, 0)
  const deliveryZone = getDeliveryZoneByWard(form.delivery_ward)

  const payload: CheckoutRequest = {
    items: items.map((item) => ({
      product_id: item.productId,
      quantity: item.quantity,
      is_exchange: false,
    })),
    customer_name: form.customer_name,
    customer_phone: form.customer_phone,
    customer_email: optionalText(form.customer_email),
    delivery_address: form.delivery_address,
    delivery_ward: optionalText(form.delivery_ward),
    delivery_district: deliveryZone,
    delivery_city: form.delivery_city,
    delivery_notes: optionalText(form.delivery_notes),
    different_recipient_name: form.has_different_recipient
      ? optionalText(form.different_recipient_name)
      : null,
    different_recipient_phone: form.has_different_recipient
      ? optionalText(form.different_recipient_phone)
      : null,
    payment_method: form.payment_method,
    vat_invoice_requested: form.vat_invoice_requested,
    vat_info: form.vat_invoice_requested ? form.vat_info : null,
    customer_notes: optionalText(form.customer_notes),
    source: 'website',
    referral_conversation_id: null,
    coupon_code: couponCode,
  }

  const submit = async () => {
    if (items.length === 0) return
    idempotencyKey.current = idempotencyKey.current ?? uuidv4()
    try {
      const order = await createOrder.mutateAsync({
        data: payload,
        idempotencyKey: idempotencyKey.current,
      })
      setLastOrder(order)
      clearCart()
      resetCheckout()
      toast.success('Đặt hàng thành công')
      router.push(`/checkout/success/${order.id}`)
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Không thể tạo đơn hàng'
      toast.error(message)
    }
  }

  return (
    <div className="space-y-5 rounded-lg border bg-white p-5">
      <div className="space-y-3">
        <h2 className="text-lg font-semibold">Kiểm tra thông tin</h2>
        <div className="grid gap-3 text-sm md:grid-cols-2">
          <div>
            <p className="text-slate-600">Khách hàng</p>
            <p className="font-medium">{form.customer_name}</p>
            <p>{formatPhone(form.customer_phone)}</p>
          </div>
          <div>
            <p className="text-slate-600">Giao đến</p>
            <p className="font-medium">{form.delivery_address}</p>
            <p>{[form.delivery_ward, form.delivery_city].filter(Boolean).join(', ')}</p>
          </div>
        </div>
      </div>

      <div className="rounded-md border">
        {items.map((item) => (
          <div
            key={item.productId}
            className="flex justify-between gap-3 border-b p-3 last:border-b-0"
          >
            <span>
              {item.name} x{item.quantity}
            </span>
            <span className="font-medium">{formatPrice(item.price * item.quantity)}</span>
          </div>
        ))}
      </div>

      <Alert>
        <AlertDescription>
          Tổng tạm tính {formatPrice(subtotal)}. Phí giao hàng được tính theo địa chỉ giao hàng.
        </AlertDescription>
      </Alert>

      <div className="flex justify-between">
        <Button type="button" variant="outline" onClick={previousStep}>
          Quay lại
        </Button>
        <Button
          disabled={createOrder.isPending || items.length === 0}
          type="button"
          onClick={submit}
        >
          {createOrder.isPending ? 'Đang đặt hàng...' : 'Xác nhận đặt hàng'}
        </Button>
      </div>
    </div>
  )
}
