'use client'

import { Info } from 'lucide-react'
import { useId, useState } from 'react'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { SHOP_INFO } from '@/lib/constants'

const deliveryWardText = `Gồm 8 phường: ${SHOP_INFO.deliveryWards.join(', ')}.`

export function DeliveryAreaPopover() {
  const [open, setOpen] = useState(false)
  const descriptionId = useId()

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          aria-describedby={open ? descriptionId : undefined}
          aria-expanded={open}
          aria-label="Xem danh sách 8 phường trong khu vực giao hàng"
          className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-primary/40 text-primary transition hover:bg-primary hover:text-primary-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
          type="button"
          onBlur={() => setOpen(false)}
          onFocus={() => setOpen(true)}
          onPointerEnter={() => setOpen(true)}
          onPointerLeave={() => setOpen(false)}
        >
          <Info className="h-4 w-4" />
        </button>
      </PopoverTrigger>
      <PopoverContent
        align="center"
        className="w-[min(20rem,calc(100vw-2rem))] border-primary/20 bg-white text-slate-700"
        id={descriptionId}
        side="top"
      >
        <p className="text-sm font-medium text-slate-950">Khu vực giao hàng</p>
        <p className="mt-2 text-sm leading-6">{deliveryWardText}</p>
      </PopoverContent>
    </Popover>
  )
}
