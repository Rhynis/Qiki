'use client'

import { useState } from 'react'
import { OrderDetailDialog } from '@/components/admin/order/order-detail-dialog'
import { OrderStatusUpdater } from '@/components/admin/order/order-status-updater'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { PageHeader } from '@/components/shared/page-header'
import { useAdminOrders } from '@/lib/hooks/use-orders'
import { formatDate, formatPhone, formatPrice } from '@/lib/utils/format'
import type { Order, OrderSearchParams, OrderStatus } from '@/types/order'

export default function AdminOrdersPage() {
  const [status, setStatus] = useState<OrderStatus | ''>('')
  const [search, setSearch] = useState('')
  const [applied, setApplied] = useState<OrderSearchParams>({ limit: 50 })
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null)
  const { data, isLoading } = useAdminOrders(applied)

  return (
    <section className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <PageHeader
        title="Quản lý đơn hàng"
        description="Lọc, kiểm tra và cập nhật trạng thái đơn."
      />
      <div className="flex flex-wrap gap-3 rounded-lg border bg-white p-4">
        <Input
          className="w-full sm:w-72"
          placeholder="Mã đơn, tên, SĐT"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        <select
          className="h-10 rounded-md border bg-white px-3 text-sm"
          value={status}
          onChange={(event) => setStatus(event.target.value as OrderStatus | '')}
        >
          <option value="">Tất cả trạng thái</option>
          <option value="pending">pending</option>
          <option value="confirmed">confirmed</option>
          <option value="shipping">shipping</option>
          <option value="delivered">delivered</option>
          <option value="cancelled">cancelled</option>
        </select>
        <Button onClick={() => setApplied({ limit: 50, search, status: status || undefined })}>
          Lọc
        </Button>
      </div>
      <div className="overflow-x-auto rounded-lg border bg-white">
        <table className="w-full min-w-[840px] text-sm">
          <thead className="bg-slate-100 text-left">
            <tr>
              <th className="p-3">Mã đơn</th>
              <th className="p-3">Khách hàng</th>
              <th className="p-3">Ngày đặt</th>
              <th className="p-3">Tổng</th>
              <th className="p-3">Trạng thái</th>
              <th className="p-3">Cập nhật</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td className="p-3 text-slate-600" colSpan={6}>
                  Đang tải...
                </td>
              </tr>
            ) : null}
            {data?.items.map((order) => (
              <tr
                key={order.id}
                className="cursor-pointer border-t transition hover:bg-slate-50"
                onClick={() => setSelectedOrder(order)}
              >
                <td className="p-3 font-medium text-primary">{order.order_number}</td>
                <td className="p-3">
                  <p>{order.customer_name}</p>
                  <p className="text-slate-600">{formatPhone(order.customer_phone)}</p>
                </td>
                <td className="p-3">{formatDate(order.created_at)}</td>
                <td className="p-3">{formatPrice(order.total_amount)}</td>
                <td className="p-3">{order.status}</td>
                <td className="p-3" onClick={(event) => event.stopPropagation()}>
                  <OrderStatusUpdater order={order} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <OrderDetailDialog
        order={selectedOrder}
        open={selectedOrder !== null}
        onOpenChange={(open) => {
          if (!open) setSelectedOrder(null)
        }}
      />
    </section>
  )
}
