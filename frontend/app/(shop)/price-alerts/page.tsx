import type { Metadata } from 'next'
import { getTranslations } from 'next-intl/server'
import { PriceAlertSubscribeForm } from '@/components/price-alerts/subscribe-form'

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations('priceAlerts')
  return { title: `${t('subscribeTitle')} | Gas Quốc Cường` }
}

export default async function PriceAlertsPage() {
  const t = await getTranslations('priceAlerts')
  return (
    <div className="mx-auto max-w-md space-y-6 px-4 py-10">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">{t('subscribeTitle')}</h1>
        <p className="text-sm text-slate-600">{t('subscribeIntro')}</p>
      </div>
      <PriceAlertSubscribeForm />
    </div>
  )
}
