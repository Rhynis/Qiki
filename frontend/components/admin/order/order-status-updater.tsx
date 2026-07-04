'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { ORDER_STATUS_LABELS_VI } from '@/lib/constants'
import { useUpdateOrderStatus } from '@/lib/hooks/use-orders'
import type { Order, OrderStatus } from '@/types/order'

const transitions: Record<OrderStatus, OrderStatus[]> = {
  pending: ['confirmed', 'cancelled'],
  confirmed: ['shipping', 'cancelled'],
  shipping: ['delivered', 'cancelled'],
  delivered: [],
  cancelled: [],
}

export function OrderStatusUpdater({ order }: { order: Order }) {
  const options = transitions[order.status]
  const [nextStatus, setNextStatus] = useState<OrderStatus>(options[0] ?? order.status)
  const mutation = useUpdateOrderStatus()

  if (options.length === 0) {
    return <span className="text-sm text-slate-500">Không còn chuyển trạng thái</span>
  }

  return (
    <div className="flex items-center gap-2">
      <select
        className="h-9 rounded-md border bg-white px-2 text-sm"
        value={nextStatus}
        onChange={(event) => setNextStatus(event.target.value as OrderStatus)}
      >
        {options.map((status) => (
          <option key={status} value={status}>
            {ORDER_STATUS_LABELS_VI[status] ?? status}
          </option>
        ))}
      </select>
      <Button
        disabled={mutation.isPending}
        size="sm"
        onClick={() =>
          mutation.mutate({
            orderId: order.id,
            data: { new_status: nextStatus },
          })
        }
      >
        Cập nhật
      </Button>
    </div>
  )
}
