import { MessageCircle, Phone } from 'lucide-react'
import { SHOP_INFO } from '@/lib/constants'

export function FloatingContact() {
  return (
    <div className="fixed bottom-6 right-24 z-40 flex items-center gap-2 md:right-28">
      <a
        aria-label={`Gọi đặt gas ${SHOP_INFO.hotline.label}`}
        className="inline-flex h-12 items-center gap-2 rounded-full bg-slate-950 px-4 text-sm font-semibold text-white shadow-lg shadow-slate-950/20 transition hover:bg-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-500 focus-visible:ring-offset-2"
        href={SHOP_INFO.hotline.href}
      >
        <Phone className="h-4 w-4" />
        <span className="hidden sm:inline">Gọi</span>
      </a>
      <a
        aria-label="Nhắn Zalo Gas Quốc Cường"
        className="inline-flex h-12 items-center gap-2 rounded-full border border-sky-200 bg-sky-600 px-4 text-sm font-semibold text-white shadow-lg shadow-sky-900/20 transition hover:bg-sky-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2"
        href={SHOP_INFO.zalo.href}
        rel="noreferrer"
        target="_blank"
      >
        <MessageCircle className="h-4 w-4" />
        <span className="hidden sm:inline">Zalo</span>
      </a>
    </div>
  )
}
