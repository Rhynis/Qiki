'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ChevronDown, Flame, Phone, ShoppingCart, Droplets } from 'lucide-react'
import { useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { UserMenu } from '@/components/shared/user-menu'
import { SHOP_INFO } from '@/lib/constants'
import { useCartStore } from '@/lib/stores/cart-store'

export function Header() {
  const router = useRouter()
  const itemCount = useCartStore((state) => state.getItemCount())
  const [productMenuOpen, setProductMenuOpen] = useState(false)
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  function openProductMenu() {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current)
      closeTimerRef.current = null
    }
    setProductMenuOpen(true)
  }

  function scheduleProductMenuClose() {
    if (closeTimerRef.current) clearTimeout(closeTimerRef.current)
    closeTimerRef.current = setTimeout(() => {
      setProductMenuOpen(false)
      closeTimerRef.current = null
    }, 150)
  }

  return (
    <header className="border-b bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-2 px-3 py-4 sm:px-4">
        <Link href="/" className="text-base font-semibold text-slate-950 sm:text-lg">
          Gas Quốc Cường
        </Link>
        <nav className="flex items-center gap-1.5 text-sm sm:gap-3">
          <div
            className="flex items-center"
            onMouseEnter={openProductMenu}
            onMouseLeave={scheduleProductMenuClose}
          >
            <DropdownMenu modal={false} open={productMenuOpen} onOpenChange={setProductMenuOpen}>
              <Link
                className="inline-flex h-9 items-center rounded-l-md px-2 font-medium text-slate-700 transition hover:bg-slate-100 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                href="/products"
              >
                Sản phẩm
              </Link>
              <DropdownMenuTrigger asChild>
                <button
                  aria-label="Mở danh mục sản phẩm"
                  className="inline-flex h-9 items-center rounded-r-md px-1.5 font-medium text-slate-700 transition hover:bg-slate-100 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  type="button"
                >
                  <ChevronDown aria-hidden="true" className="h-4 w-4" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="start"
                onMouseEnter={openProductMenu}
                onMouseLeave={scheduleProductMenuClose}
              >
                <DropdownMenuItem
                  className="cursor-pointer rounded-md hover:bg-primary/10 hover:text-primary focus:bg-primary/10 focus:text-primary"
                  onSelect={() => router.push('/products?category=gas')}
                >
                  <Flame className="h-4 w-4 text-primary" />
                  Gas
                </DropdownMenuItem>
                <DropdownMenuItem
                  className="cursor-pointer rounded-md hover:bg-primary/10 hover:text-primary focus:bg-primary/10 focus:text-primary"
                  onSelect={() => router.push('/products?category=nuoc_uong')}
                >
                  <Droplets className="h-4 w-4 text-primary" />
                  Nước Uống
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          <Link href="/track">Tra cứu</Link>
          <a
            className="hidden items-center gap-2 rounded-md border border-slate-200 px-3 py-2 font-medium text-slate-700 transition hover:bg-slate-100 hover:text-slate-950 md:inline-flex"
            href={SHOP_INFO.hotline.href}
          >
            <Phone className="h-4 w-4" />
            {SHOP_INFO.hotline.label}
          </a>
          <Button asChild size="icon" variant="ghost">
            <Link aria-label="Giỏ hàng" className="relative" href="/cart">
              <ShoppingCart className="h-5 w-5" />
              {itemCount > 0 ? (
                <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-semibold text-primary-foreground">
                  {itemCount}
                </span>
              ) : null}
            </Link>
          </Button>
          <UserMenu />
        </nav>
      </div>
    </header>
  )
}
