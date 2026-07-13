'use client'

import { useTranslations } from 'next-intl'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/shared/page-header'
import { useMyOrders } from '@/lib/hooks/use-orders'
import { formatDate, formatPrice } from '@/lib/utils/format'
import type { OrderStatus } from '@/types/order'

export default function OrdersPage() {
  const t = useTranslations('orders')
  const tStatus = useTranslations('orderStatus')
  const tCommon = useTranslations('common')
  const { data, isLoading, isError } = useMyOrders({ limit: 50 })

  return (
    <section className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <PageHeader title={t('title')} description={t('description')} />
      <div className="rounded-lg border bg-white">
        {isLoading ? <p className="p-4 text-sm text-slate-600">{tCommon('loading')}</p> : null}
        {isError ? <p className="p-4 text-sm text-red-700">{t('loadError')}</p> : null}
        {data?.items.length === 0 ? (
          <div className="space-y-3 p-6 text-center">
            <p className="text-slate-600">{t('empty')}</p>
            <Button asChild>
              <Link href="/products">{t('viewProducts')}</Link>
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
            <span className="text-sm">{tStatus(order.status as OrderStatus)}</span>
            <span className="font-semibold md:text-right">{formatPrice(order.total_amount)}</span>
          </Link>
        ))}
      </div>
    </section>
  )
}
