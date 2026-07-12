'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { OrderStatusTimeline } from '@/components/shop/order/order-status-timeline'
import { PageHeader } from '@/components/shared/page-header'
import { useCancelOrder, useOrder } from '@/lib/hooks/use-orders'
import { deliveryItemLines, deliveryStatusLabels } from '@/lib/utils/delivery'
import { formatDate, formatPhone, formatPrice } from '@/lib/utils/format'

export function OrderDetailClient({ orderId }: { orderId: string }) {
  const [phone, setPhone] = useState('')
  const [verifiedPhone, setVerifiedPhone] = useState<string | undefined>(undefined)
  const { data: order, isLoading, isError } = useOrder(orderId, verifiedPhone)
  const cancelOrder = useCancelOrder()
  const canCancel = order?.status === 'pending' || order?.status === 'confirmed'

  const verifyPhone = () => {
    setVerifiedPhone(phone)
  }

  const submitCancel = async () => {
    if (!order) return
    if (!window.confirm('Hủy đơn hàng này?')) return
    await cancelOrder.mutateAsync({
      orderId: order.id,
      data: { phone: verifiedPhone, reason: 'Customer cancelled from website' },
    })
  }

  return (
    <section className="mx-auto max-w-4xl space-y-6 px-4 py-8">
      <PageHeader title="Chi tiết đơn hàng" />
      {isLoading ? <p className="text-sm text-slate-600">Đang tải...</p> : null}
      {isError ? (
        <div className="space-y-3 rounded-lg border bg-white p-4">
          <p className="text-sm text-slate-600">Nhập số điện thoại đặt hàng để xem đơn.</p>
          <div className="flex gap-2">
            <Input value={phone} onChange={(event) => setPhone(event.target.value)} />
            <Button onClick={verifyPhone}>Xem</Button>
          </div>
        </div>
      ) : null}
      {order ? (
        <div className="space-y-5 rounded-lg border bg-white p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold">{order.order_number}</h1>
              <p className="text-sm text-slate-600">{formatDate(order.created_at)}</p>
            </div>
            {canCancel ? (
              <Button
                disabled={cancelOrder.isPending}
                type="button"
                variant="destructive"
                onClick={submitCancel}
              >
                Hủy đơn
              </Button>
            ) : null}
          </div>
          <OrderStatusTimeline status={order.status} />
          {order.deliveries.length > 0 ? (
            <div className="space-y-2">
              <h2 className="font-semibold">Tiến độ giao hàng</h2>
              {order.deliveries.map((delivery) => (
                <div
                  key={delivery.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-3"
                >
                  <div className="min-w-0">
                    <p className="font-mono text-sm">{delivery.code}</p>
                    <p className="text-sm text-slate-600">
                      {deliveryItemLines(order, delivery).join(', ')}
                    </p>
                    {delivery.delivered_at ? (
                      <p className="text-xs text-slate-500">
                        Đã giao: {formatDate(delivery.delivered_at)}
                      </p>
                    ) : delivery.scheduled_at ? (
                      <p className="text-xs text-slate-500">
                        Hẹn giao: {formatDate(delivery.scheduled_at)}
                      </p>
                    ) : null}
                  </div>
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
                    {deliveryStatusLabels[delivery.status] ?? delivery.status}
                  </span>
                </div>
              ))}
            </div>
          ) : null}
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <h2 className="font-semibold">Giao hàng</h2>
              <p>{order.customer_name}</p>
              <p>{formatPhone(order.customer_phone)}</p>
              <p className="text-slate-600">
                {[
                  order.delivery_address,
                  order.delivery_ward,
                  order.delivery_district,
                  order.delivery_city,
                ]
                  .filter(Boolean)
                  .join(', ')}
              </p>
            </div>
            {order.vat_invoice_requested && order.vat_info ? (
              <div>
                <h2 className="font-semibold">Hóa đơn VAT</h2>
                <p>{order.vat_info.company_name}</p>
                <p>{order.vat_info.tax_code}</p>
                <p className="text-slate-600">{order.vat_info.address}</p>
              </div>
            ) : null}
          </div>
          <div className="rounded-md border">
            {order.items.map((item) => (
              <div
                key={item.id}
                className="flex justify-between gap-3 border-b p-3 last:border-b-0"
              >
                <span>
                  {item.product_name} x{item.quantity}
                </span>
                <span className="font-medium">{formatPrice(item.subtotal)}</span>
              </div>
            ))}
          </div>
          <div className="space-y-1 text-right">
            <p className="text-sm text-slate-600">Tạm tính {formatPrice(order.subtotal)}</p>
            <p className="text-sm text-slate-600">
              Phí giao hàng {formatPrice(order.shipping_fee)}
            </p>
            <p className="text-xl font-semibold">Tổng {formatPrice(order.total_amount)}</p>
          </div>
        </div>
      ) : null}
    </section>
  )
}
