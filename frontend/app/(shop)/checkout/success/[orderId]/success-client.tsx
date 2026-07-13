'use client'

import Link from 'next/link'
import { CheckCircle2, Copy } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { useCheckoutStore } from '@/lib/stores/checkout-store'
import { formatDate, formatPrice } from '@/lib/utils/format'

export function SuccessClient({ orderId }: { orderId: string }) {
  const t = useTranslations('checkoutSuccess')
  const lastOrder = useCheckoutStore((state) => state.lastOrder)
  const order = lastOrder?.id === orderId ? lastOrder : null

  const copyOrderNumber = async () => {
    if (!order) return
    await navigator.clipboard.writeText(order.order_number)
    toast.success(t('copied'))
  }

  return (
    <section className="mx-auto max-w-3xl space-y-6 px-4 py-10">
      <div className="rounded-lg border bg-white p-6 text-center">
        <CheckCircle2 className="mx-auto h-12 w-12 text-emerald-600" />
        <h1 className="mt-4 text-3xl font-semibold tracking-normal">{t('title')}</h1>
        {order ? (
          <div className="mt-5 space-y-3">
            <div className="inline-flex items-center gap-2 rounded-md border px-4 py-2 text-lg font-semibold">
              {order.order_number}
              <Button
                aria-label={t('copyAria')}
                size="icon"
                variant="ghost"
                onClick={copyOrderNumber}
              >
                <Copy className="h-4 w-4" />
              </Button>
            </div>
            <p className="text-slate-600">
              {t('estimate', { amount: formatPrice(order.total_amount) })}
            </p>
            <p className="text-sm text-slate-600">
              {t('orderDate', { date: formatDate(order.created_at) })}
            </p>
            {order.user_id ? null : (
              <p className="rounded-md bg-slate-100 p-3 text-sm">{t('guestNotice')}</p>
            )}
          </div>
        ) : (
          <p className="mt-4 text-slate-600">{t('recorded')}</p>
        )}
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Button asChild>
            <Link href={order ? `/orders/${order.id}` : '/track'}>{t('trackOrder')}</Link>
          </Button>
          {!order?.user_id ? (
            <Button asChild variant="outline">
              <Link href="/register">{t('createAccount')}</Link>
            </Button>
          ) : null}
        </div>
      </div>
    </section>
  )
}
