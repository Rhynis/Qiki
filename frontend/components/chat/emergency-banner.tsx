'use client'

import { AlertTriangle, Phone } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { SHOP_INFO } from '@/lib/constants'

export function EmergencyBanner() {
  const t = useTranslations('chat')
  return (
    <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <div className="space-y-1">
          <p className="font-semibold">{t('emergencyTitle')}</p>
          <p>{t('emergencyBody')}</p>
          <a className="inline-flex items-center gap-1 font-semibold" href={SHOP_INFO.hotline.href}>
            <Phone className="h-4 w-4" />
            {SHOP_INFO.hotline.label}
          </a>
        </div>
      </div>
    </div>
  )
}
