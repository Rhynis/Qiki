'use client'

import { Headphones } from 'lucide-react'
import { useTranslations } from 'next-intl'

type EscalationNoticeProps = {
  reason?: string | null
}

export function EscalationNotice({ reason }: EscalationNoticeProps) {
  const t = useTranslations('chat')
  return (
    <div className="rounded-md border border-sky-200 bg-sky-50 p-3 text-sm text-sky-900">
      <div className="flex items-start gap-2">
        <Headphones className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <p className="font-semibold">{t('escalationTitle')}</p>
          <p>{reason ?? t('escalationDefault')}</p>
        </div>
      </div>
    </div>
  )
}
