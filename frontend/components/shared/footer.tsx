import Link from 'next/link'
import { Clock, ExternalLink, MapPin, MessageCircle, Phone } from 'lucide-react'
import { OpeningHoursBadge } from '@/components/shared/opening-hours-badge'
import { SHOP_INFO } from '@/lib/constants'

export function Footer() {
  return (
    <footer className="border-t bg-white">
      <div className="mx-auto grid max-w-6xl gap-7 px-4 py-8 text-sm text-slate-600 md:grid-cols-2 lg:grid-cols-[1fr_0.9fr_1.15fr_1.25fr]">
        <div>
          <p className="text-base font-semibold text-slate-950">{SHOP_INFO.name}</p>
          <p className="mt-2 max-w-sm">
            Giao gas LPG tận nơi tại {SHOP_INFO.deliveryAreaLabel}, hỗ trợ đặt hàng qua trợ lý ảo,
            hotline và Zalo.
          </p>
          <Link
            className="mt-4 inline-block font-medium text-primary hover:underline"
            href="/products"
          >
            Xem sản phẩm
          </Link>
        </div>
        <div className="space-y-2">
          <p className="font-semibold text-slate-950">Liên hệ</p>
          <div className="flex flex-wrap items-center gap-2">
            <a
              className="inline-flex items-center gap-2 font-medium text-slate-900 hover:text-primary"
              href={SHOP_INFO.hotline.href}
            >
              <Phone className="h-4 w-4" />
              {SHOP_INFO.hotline.label}
            </a>
            <a
              aria-label="Nhắn Zalo Gas Quốc Cường"
              className="inline-flex items-center gap-1 rounded-full border border-primary/25 px-2 py-1 text-xs font-semibold text-primary hover:bg-primary hover:text-primary-foreground"
              href={SHOP_INFO.zalo.href}
              rel="noreferrer"
              target="_blank"
            >
              <MessageCircle className="h-3.5 w-3.5" />
              Zalo
            </a>
          </div>
          <a className="block hover:text-slate-950" href={SHOP_INFO.landline.href}>
            Số bàn: {SHOP_INFO.landline.label}
          </a>
        </div>
        <div className="space-y-3">
          <p className="font-semibold text-slate-950">Cửa hàng</p>
          <div className="flex items-start gap-2">
            <Clock className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <div className="space-y-2">
              <OpeningHoursBadge />
              <div className="space-y-1">
                <p>
                  <span className="font-medium text-slate-900">
                    {SHOP_INFO.hours.weekdaysLabel}
                  </span>
                  <span className="block">{SHOP_INFO.hours.weekdaysTime}</span>
                </p>
                <p>
                  <span className="font-medium text-slate-900">
                    {SHOP_INFO.hours.weekendsLabel}
                  </span>
                  <span className="block">{SHOP_INFO.hours.weekendsTime}</span>
                </p>
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <div>
              <p className="text-slate-900">{SHOP_INFO.address}</p>
              <p className="mt-1 text-xs text-slate-500">Địa chỉ cũ: {SHOP_INFO.addressOld}</p>
            </div>
          </div>
        </div>
        <div className="space-y-3">
          <p className="font-semibold text-slate-950">Bản đồ cửa hàng</p>
          <iframe
            allowFullScreen
            className="h-[260px] w-full rounded-md border"
            loading="lazy"
            referrerPolicy="no-referrer-when-downgrade"
            src={SHOP_INFO.map.embedSrc}
            title="Bản đồ cửa hàng Gas Quốc Cường"
          />
          <a
            className="inline-flex items-center gap-2 font-medium text-primary hover:underline"
            href={SHOP_INFO.map.link}
            rel="noreferrer"
            target="_blank"
          >
            Chỉ đường
            <ExternalLink className="h-4 w-4" />
          </a>
        </div>
      </div>
    </footer>
  )
}
