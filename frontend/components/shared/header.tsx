'use client'

import Link from 'next/link'
import { ChevronDown, Flame, Phone, ShoppingCart, Droplets } from 'lucide-react'
import { useState } from 'react'
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
  const itemCount = useCartStore((state) => state.getItemCount())
  const [productMenuOpen, setProductMenuOpen] = useState(false)

  return (
    <header className="border-b bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
        <Link href="/" className="text-lg font-semibold text-slate-950">
          Gas Quốc Cường
        </Link>
        <nav className="flex items-center gap-3 text-sm">
          <div className="flex items-center" onMouseEnter={() => setProductMenuOpen(true)}>
            <Link
              href="/products"
              className="rounded-md px-2 py-2 font-medium text-slate-700 transition hover:text-primary"
            >
              Sản phẩm
            </Link>
            <DropdownMenu open={productMenuOpen} onOpenChange={setProductMenuOpen}>
              <DropdownMenuTrigger asChild>
                <button
                  aria-label="Mở danh mục sản phẩm"
                  className="inline-flex h-8 w-8 items-center justify-center rounded-md text-slate-600 transition hover:bg-slate-100 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  type="button"
                >
                  <ChevronDown className="h-4 w-4" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start">
                <DropdownMenuItem asChild>
                  <Link href="/products?category=gas">
                    <Flame className="h-4 w-4 text-primary" />
                    Gas
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link href="/products?category=nuoc_uong">
                    <Droplets className="h-4 w-4 text-primary" />
                    Nước Uống
                  </Link>
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
