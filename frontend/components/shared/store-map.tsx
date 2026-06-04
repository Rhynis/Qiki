'use client'

import { useState } from 'react'
import { SHOP_INFO } from '@/lib/constants'

/**
 * Bản đồ cửa hàng. Iframe bị tắt pointer-events đến khi người dùng bấm vào, để
 * tránh map "nuốt" thao tác cuộn trang khi con trỏ đi ngang qua (scroll-trap).
 */
export function StoreMap() {
  const [active, setActive] = useState(false)

  return (
    <div className="relative h-[260px] w-full overflow-hidden rounded-md border">
      <iframe
        allowFullScreen
        className={active ? 'h-full w-full' : 'pointer-events-none h-full w-full'}
        loading="lazy"
        referrerPolicy="no-referrer-when-downgrade"
        src={SHOP_INFO.map.embedSrc}
        title="Bản đồ cửa hàng Gas Quốc Cường"
      />
      {!active ? (
        <button
          aria-label="Bật tương tác bản đồ"
          className="absolute inset-0 flex items-end justify-center bg-transparent pb-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
          type="button"
          onClick={() => setActive(true)}
        >
          <span className="rounded-full bg-slate-900/80 px-3 py-1 text-xs font-medium text-white">
            Bấm để tương tác bản đồ
          </span>
        </button>
      ) : null}
    </div>
  )
}
