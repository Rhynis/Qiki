'use client'

import { useTranslations } from 'next-intl'
import { useState } from 'react'
import { SHOP_INFO } from '@/lib/constants'

/**
 * Store map. The iframe has pointer-events disabled until the user clicks it, to
 * keep the map from "swallowing" page scroll when the cursor passes over it (scroll-trap).
 */
export function StoreMap() {
  const t = useTranslations('shared')
  const [active, setActive] = useState(false)

  return (
    <div className="relative h-[260px] w-full overflow-hidden rounded-md border">
      <iframe
        allowFullScreen
        className={active ? 'h-full w-full' : 'pointer-events-none h-full w-full'}
        loading="lazy"
        referrerPolicy="no-referrer-when-downgrade"
        src={SHOP_INFO.map.embedSrc}
        title={t('mapTitle')}
      />
      {!active ? (
        <button
          aria-label={t('mapInteractAria')}
          className="absolute inset-0 flex items-end justify-center bg-transparent pb-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
          type="button"
          onClick={() => setActive(true)}
        >
          <span className="rounded-full bg-slate-900/80 px-3 py-1 text-xs font-medium text-white">
            {t('mapInteractHint')}
          </span>
        </button>
      ) : null}
    </div>
  )
}
