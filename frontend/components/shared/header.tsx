'use client'

import Link from 'next/link'
import { ShoppingCart } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { UserMenu } from '@/components/shared/user-menu'
import { useCartStore } from '@/lib/stores/cart-store'

export function Header() {
  const itemCount = useCartStore((state) => state.getItemCount())

  return (
    <header className="border-b bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
        <Link href="/" className="text-lg font-semibold text-slate-950">
          Gas Quốc Cường
        </Link>
        <nav className="flex items-center gap-3 text-sm">
          <Link href="/products">Sản phẩm</Link>
          <Link href="/track">Tra cứu</Link>
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
