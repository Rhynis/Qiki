'use client'

import { useTranslations } from 'next-intl'
import { useState } from 'react'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { PageHeader } from '@/components/shared/page-header'
import { useLookupOrder } from '@/lib/hooks/use-orders'
import { sanitizeOrderNumberForLookup } from '@/lib/utils/order-lookup'
import { formatPhone } from '@/lib/utils/format'
import { guestLookupSchema } from '@/lib/validations/order'
import type { OrderStatus } from '@/types/order'

export default function TrackOrderPage() {
  const t = useTranslations('track')
  const tStatus = useTranslations('orderStatus')
  const [orderNumber, setOrderNumber] = useState('')
  const [phone, setPhone] = useState('')
  const [error, setError] = useState<string | null>(null)
  const lookup = useLookupOrder()
  const lookupError = error ?? (lookup.isError ? t('notFound') : null)

  const submit = async () => {
    lookup.reset()
    const result = guestLookupSchema.safeParse({
      order_number: sanitizeOrderNumberForLookup(orderNumber),
      phone: phone.trim(),
    })
    if (!result.success) {
      setError(result.error.issues[0]?.message ?? t('invalidInput'))
      return
    }
    setError(null)
    try {
      await lookup.mutateAsync(result.data)
    } catch {
      setError(t('notFound'))
    }
  }

  return (
    <section className="mx-auto max-w-xl space-y-6 px-4 py-8">
      <PageHeader title={t('title')} description={t('description')} />
      <div className="space-y-4 rounded-lg border bg-white p-5">
        <div className="space-y-2">
          <Label htmlFor="order_number">{t('orderNumber')}</Label>
          <Input
            id="order_number"
            value={orderNumber}
            onChange={(event) => setOrderNumber(event.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="phone">{t('phone')}</Label>
          <Input id="phone" value={phone} onChange={(event) => setPhone(event.target.value)} />
        </div>
        {lookupError ? <p className="text-sm text-red-700">{lookupError}</p> : null}
        <Button disabled={lookup.isPending} onClick={submit}>
          {lookup.isPending ? t('looking') : t('lookup')}
        </Button>
      </div>
      {lookup.data ? (
        <div className="rounded-lg border bg-white p-5">
          <p className="font-semibold">{lookup.data.order_number}</p>
          <p className="text-sm text-slate-600">
            {t('phoneLabel', { phone: formatPhone(lookup.data.customer_phone) })}
          </p>
          <p className="text-sm text-slate-600">
            {t('statusLabel', { status: tStatus(lookup.data.status as OrderStatus) })}
          </p>
          <Button asChild className="mt-3" variant="outline">
            <Link href={`/orders/${lookup.data.id}`}>{t('viewDetails')}</Link>
          </Button>
        </div>
      ) : null}
    </section>
  )
}
