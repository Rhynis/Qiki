'use client'

import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/shared/page-header'
import { ORDER_STATUS_LABELS_VI } from '@/lib/constants'
import { useMyOrders } from '@/lib/hooks/use-orders'
import { formatDate, formatPrice } from '@/lib/utils/format'

export default function OrdersPage() {
  const { data, isLoading, isError } = useMyOrders({ limit: 50 })

  return (
    <section className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <PageHeader title="Đơn hàng của tôi" description="Theo dõi các đơn gas đã đặt." />
      <div className="rounded-lg border bg-white">
        {isLoading ? <p className="p-4 text-sm text-slate-600">Đang tải...</p> : null}
        {isError ? <p className="p-4 text-sm text-red-700">Không thể tải đơn hàng.</p> : null}
        {data?.items.length === 0 ? (
          <div className="space-y-3 p-6 text-center">
            <p className="text-slate-600">Chưa có đơn hàng.</p>
            <Button asChild>
              <Link href="/products">Xem sản phẩm</Link>
            </Button>
          </div>
        ) : null}
        {data?.items.map((order) => (
          <Link
            key={order.id}
            className="grid gap-2 border-b p-4 hover:bg-slate-50 md:grid-cols-[1fr_140px_140px] md:items-center"
            href={`/orders/${order.id}`}
          >
            <div>
              <p className="font-medium">{order.order_number}</p>
              <p className="text-sm text-slate-600">{formatDate(order.created_at)}</p>
            </div>
            <span className="text-sm">{ORDER_STATUS_LABELS_VI[order.status] ?? order.status}</span>
            <span className="font-semibold md:text-right">{formatPrice(order.total_amount)}</span>
          </Link>
        ))}
      </div>
    </section>
  )
}
