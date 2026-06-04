'use client'

import { Info } from 'lucide-react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { SHOP_INFO } from '@/lib/constants'

const deliveryWardText = `Gồm 8 phường: ${SHOP_INFO.deliveryWards.join(', ')}.`

export function DeliveryAreaPopover() {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          aria-label="Xem danh sách 8 phường trong khu vực giao hàng"
          className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-white/25 text-slate-300 transition hover:border-primary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
          type="button"
        >
          <Info className="h-4 w-4" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="center"
        className="w-[min(20rem,calc(100vw-2rem))] border-primary/20 bg-white text-slate-700"
        side="top"
      >
        <p className="text-sm font-medium text-slate-950">Khu vực giao hàng</p>
        <p className="mt-2 text-sm leading-6">{deliveryWardText}</p>
      </PopoverContent>
    </Popover>
  )
}
