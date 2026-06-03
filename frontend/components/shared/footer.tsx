import Link from 'next/link'
import { Clock, MapPin, Phone } from 'lucide-react'
import { SHOP_INFO } from '@/lib/constants'

export function Footer() {
  return (
    <footer className="border-t bg-white">
      <div className="mx-auto grid max-w-6xl gap-6 px-4 py-8 text-sm text-slate-600 md:grid-cols-[1.2fr_1fr_1fr]">
        <div>
          <p className="text-base font-semibold text-slate-950">{SHOP_INFO.name}</p>
          <p className="mt-2 max-w-sm">
            Giao gas LPG tận nơi tại {SHOP_INFO.deliveryAreaLabel}, hỗ trợ đặt hàng qua Qiki,
            hotline và Zalo.
          </p>
        </div>
        <div className="space-y-2">
          <p className="font-semibold text-slate-950">Liên hệ</p>
          <a className="flex items-center gap-2 hover:text-slate-950" href={SHOP_INFO.hotline.href}>
            <Phone className="h-4 w-4" />
            {SHOP_INFO.hotline.label}
          </a>
          <a className="block hover:text-slate-950" href={SHOP_INFO.landline.href}>
            Số bàn: {SHOP_INFO.landline.label}
          </a>
          <a
            className="block hover:text-slate-950"
            href={SHOP_INFO.zalo.href}
            rel="noreferrer"
            target="_blank"
          >
            {SHOP_INFO.zalo.label}
          </a>
        </div>
        <div className="space-y-2">
          <p className="font-semibold text-slate-950">Cửa hàng</p>
          <p className="flex gap-2">
            <Clock className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{SHOP_INFO.hours.summary}</span>
          </p>
          <p className="flex gap-2">
            <MapPin className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{SHOP_INFO.address}</span>
          </p>
          <Link
            className="inline-block font-medium text-slate-950 hover:underline"
            href="/products"
          >
            Xem sản phẩm
          </Link>
        </div>
      </div>
    </footer>
  )
}
