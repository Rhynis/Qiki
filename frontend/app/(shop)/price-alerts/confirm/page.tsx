import type { Metadata } from 'next'
import { getTranslations } from 'next-intl/server'
import { Suspense } from 'react'
import { TokenActionClient } from '@/components/price-alerts/token-action-client'

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations('priceAlerts')
  return { title: `${t('confirmTitle')} | Gas Quốc Cường` }
}

export default async function ConfirmPriceAlertsPage() {
  const t = await getTranslations('priceAlerts')
  return (
    <div className="mx-auto max-w-md space-y-6 px-4 py-10">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">{t('confirmTitle')}</h1>
        <p className="text-sm text-slate-600">{t('confirmIntro')}</p>
      </div>
      <Suspense fallback={null}>
        <TokenActionClient variant="confirm" />
      </Suspense>
    </div>
  )
}
