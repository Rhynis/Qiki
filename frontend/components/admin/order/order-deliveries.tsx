'use client'

import { Truck } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { useCreateDelivery, useUpdateDeliveryStatus } from '@/lib/hooks/use-orders'
import { formatDate } from '@/lib/utils/format'
import {
  allocatedByOrderItem,
  deliveryItemLines,
  deliveryStatusLabels,
  deliveryStatusTransitions,
} from '@/lib/utils/delivery'
import type { DeliveryStatus, Order } from '@/types/order'

export function OrderDeliveries({ order }: { order: Order }) {
  const createDelivery = useCreateDelivery()
  const updateStatus = useUpdateDeliveryStatus()
  const allocated = useMemo(() => allocatedByOrderItem(order), [order])
  const [quantities, setQuantities] = useState<Record<string, string>>({})

  const remainingByItem = order.items.map((item) => ({
    item,
    remaining: item.quantity - (allocated[item.id] ?? 0),
  }))
  const hasRemaining = remainingByItem.some((entry) => entry.remaining > 0)

  const submit = () => {
    const items = order.items
      .map((item) => ({
        order_item_id: item.id,
        quantity: Number.parseInt(quantities[item.id] ?? '', 10),
      }))
      .filter((line) => Number.isInteger(line.quantity) && line.quantity > 0)
    if (items.length === 0) return
    createDelivery.mutate(
      { orderId: order.id, data: { items } },
      { onSuccess: () => setQuantities({}) }
    )
  }

  return (
    <section className="space-y-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Chuyến giao</p>

      {order.deliveries.length === 0 ? (
        <p className="text-sm text-slate-500">Chưa có chuyến giao nào.</p>
      ) : (
        <div className="space-y-2">
          {order.deliveries.map((delivery) => (
            <div key={delivery.id} className="rounded-md border p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Truck className="h-4 w-4 text-primary" />
                  <span className="font-mono text-sm">{delivery.code}</span>
                  <Badge variant="outline">
                    {deliveryStatusLabels[delivery.status] ?? delivery.status}
                  </Badge>
                </div>
                {deliveryStatusTransitions[delivery.status].length > 0 ? (
                  <select
                    className="h-8 rounded-md border bg-white px-2 text-sm"
                    aria-label={`Đổi trạng thái ${delivery.code}`}
                    value=""
                    disabled={updateStatus.isPending}
                    onChange={(event) => {
                      const next = event.target.value as DeliveryStatus
                      if (!next) return
                      updateStatus.mutate({
                        orderId: order.id,
                        deliveryId: delivery.id,
                        data: { status: next },
                      })
                    }}
                  >
                    <option value="">Đổi trạng thái…</option>
                    {deliveryStatusTransitions[delivery.status].map((next) => (
                      <option key={next} value={next}>
                        {deliveryStatusLabels[next]}
                      </option>
                    ))}
                  </select>
                ) : null}
              </div>
              <p className="mt-1 text-sm text-slate-600">
                {deliveryItemLines(order, delivery).join(', ')}
              </p>
              {delivery.scheduled_at ? (
                <p className="text-xs text-slate-500">Hẹn giao: {formatDate(delivery.scheduled_at)}</p>
              ) : null}
              {delivery.delivered_at ? (
                <p className="text-xs text-slate-500">Đã giao: {formatDate(delivery.delivered_at)}</p>
              ) : null}
            </div>
          ))}
        </div>
      )}

      {hasRemaining ? (
        <div className="rounded-md border border-dashed p-3">
          <p className="mb-2 text-sm font-medium text-slate-900">Tạo chuyến giao mới</p>
          <div className="space-y-2">
            {remainingByItem
              .filter((entry) => entry.remaining > 0)
              .map(({ item, remaining }) => (
                <div key={item.id} className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm text-slate-900">{item.product_name}</p>
                    <p className="text-xs text-slate-500">Còn lại: {remaining}</p>
                  </div>
                  <Input
                    type="number"
                    min={0}
                    max={remaining}
                    className="h-8 w-20"
                    aria-label={`Số lượng ${item.product_name}`}
                    value={quantities[item.id] ?? ''}
                    onChange={(event) =>
                      setQuantities((prev) => ({ ...prev, [item.id]: event.target.value }))
                    }
                  />
                </div>
              ))}
          </div>
          <Button
            type="button"
            size="sm"
            className="mt-3"
            disabled={createDelivery.isPending}
            onClick={submit}
          >
            Tạo chuyến giao
          </Button>
        </div>
      ) : null}
    </section>
  )
}
