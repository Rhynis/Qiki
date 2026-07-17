'use client'

import Link from 'next/link'
import { useTranslations } from 'next-intl'
import { useSearchParams } from 'next/navigation'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { confirmPriceAlerts, unsubscribePriceAlerts } from '@/lib/api/price-alerts'

type Variant = 'confirm' | 'unsubscribe'

const ACTIONS: Record<Variant, (token: string) => Promise<{ message: string }>> = {
  confirm: confirmPriceAlerts,
  unsubscribe: unsubscribePriceAlerts,
}

type Status = 'idle' | 'pending' | 'done' | 'error'

/**
 * Renders an explicit confirm/unsubscribe button driven by the ``token`` query
 * param. The action is button-triggered (not run on mount) so email clients or
 * link scanners cannot silently confirm or unsubscribe an address.
 */
export function TokenActionClient({ variant }: { variant: Variant }) {
  const t = useTranslations('priceAlerts')
  const action = ACTIONS[variant]
  const actionLabel = variant === 'confirm' ? t('confirmAction') : t('unsubscribeAction')
  const pendingLabel = variant === 'confirm' ? t('confirmPending') : t('unsubscribePending')
  const invalidMessage = variant === 'confirm' ? t('confirmInvalid') : t('unsubscribeInvalid')
  const token = useSearchParams().get('token') ?? ''
  const [status, setStatus] = useState<Status>('idle')
  const [message, setMessage] = useState<string | null>(null)

  if (!token) {
    return <p className="text-sm text-red-600">{invalidMessage}</p>
  }

  const handleClick = async () => {
    setStatus('pending')
    setMessage(null)
    try {
      const result = await action(token)
      setStatus('done')
      setMessage(result.message)
    } catch (caught) {
      setStatus('error')
      setMessage(caught instanceof Error ? caught.message : invalidMessage)
    }
  }

  if (status === 'done') {
    return (
      <div className="space-y-4">
        <p className="text-sm text-emerald-700">{message}</p>
        <Link className="inline-block text-sm text-primary hover:underline" href="/products">
          {t('viewProducts')}
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {status === 'error' && message ? <p className="text-sm text-red-600">{message}</p> : null}
      <Button disabled={status === 'pending'} onClick={() => void handleClick()} type="button">
        {status === 'pending' ? pendingLabel : actionLabel}
      </Button>
    </div>
  )
}
