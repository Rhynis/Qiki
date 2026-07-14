import { Phone } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { ZaloIcon } from '@/components/icons/zalo-icon'
import { SHOP_INFO } from '@/lib/constants'

export function FloatingContact() {
  const t = useTranslations('shared')
  return (
    <div className="fixed bottom-6 right-24 z-40 flex items-center gap-2 md:right-28">
      <a
        aria-label={t('callToOrderAria', { phone: SHOP_INFO.hotline.label })}
        className="inline-flex h-12 items-center gap-2 rounded-full bg-primary px-4 text-sm font-semibold text-primary-foreground shadow-lg shadow-primary/20 transition hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        href={SHOP_INFO.hotline.href}
      >
        <Phone className="h-4 w-4" />
        <span className="hidden sm:inline">{t('callShort')}</span>
      </a>
      <a
        aria-label={t('zaloAria')}
        className="inline-flex h-12 w-12 items-center justify-center rounded-2xl shadow-lg transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        href={SHOP_INFO.zalo.href}
        rel="noreferrer"
        target="_blank"
      >
        <ZaloIcon className="h-12 w-12 rounded-2xl" />
      </a>
    </div>
  )
}
