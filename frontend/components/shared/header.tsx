'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ChevronDown, Flame, Phone, ShoppingCart, Droplets } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { LanguageSwitcher } from '@/components/shared/language-switcher'
import { UserMenu } from '@/components/shared/user-menu'
import { SHOP_INFO } from '@/lib/constants'
import { useCartStore } from '@/lib/stores/cart-store'

// Shared styling for the top-level text nav items so "Sản phẩm", "Tra cứu" and
// "Cẩm nang" render as evenly spaced, consistent pills.
const navItemClass =
  'inline-flex h-9 items-center rounded-md px-2.5 font-medium text-slate-700 transition-colors hover:bg-slate-100 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'

export function Header() {
  const t = useTranslations('header')
  const tNav = useTranslations('nav')
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
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-1.5 px-2 py-4 sm:px-4">
        <Link href="/" className="text-base font-semibold text-slate-950 sm:text-lg">
          {SHOP_INFO.name}
        </Link>
        {/* Wrap on very narrow screens so an extra nav item can never push the
            header past the viewport (horizontal-scroll guard); stays a single
            row from the small breakpoint up. */}
        <nav className="flex flex-wrap items-center justify-end gap-x-1 gap-y-1 text-sm sm:gap-x-1.5">
          {/* Products: one pill that reads as a single "Sản phẩm ⌄" control — the
              label links to the full catalog, the chevron opens the category menu.
              A single hover background on the wrapper keeps them visually merged
              (no split seam) while staying two accessible controls. */}
          <div
            className="inline-flex h-9 items-center rounded-md font-medium text-slate-700 transition-colors hover:bg-slate-100 hover:text-primary"
            onMouseEnter={openProductMenu}
            onMouseLeave={scheduleProductMenuClose}
          >
            <DropdownMenu modal={false} open={productMenuOpen} onOpenChange={setProductMenuOpen}>
              <Link
                className="inline-flex h-full items-center rounded-l-md pl-2.5 pr-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                href="/products"
              >
                {t('products')}
              </Link>
              <DropdownMenuTrigger asChild>
                <button
                  aria-label={t('openCategories')}
                  className="inline-flex h-full items-center rounded-r-md pl-0.5 pr-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  type="button"
                >
                  <ChevronDown aria-hidden="true" className="h-4 w-4" />
                </button>
              </DropdownMenuTrigger>
              {/* Nudge the menu left so "Gas"/"Nước Uống" line up under the start of
                  "Sản phẩm" rather than under the chevron on the pill's right edge. */}
              <DropdownMenuContent
                align="start"
                alignOffset={-96}
                onMouseEnter={openProductMenu}
                onMouseLeave={scheduleProductMenuClose}
              >
                <DropdownMenuItem
                  className="cursor-pointer rounded-md hover:bg-primary/10 hover:text-primary focus:bg-primary/10 focus:text-primary"
                  onSelect={() => router.push('/products?category=gas')}
                >
                  <Flame className="h-4 w-4 text-primary" />
                  {t('categoryGas')}
                </DropdownMenuItem>
                <DropdownMenuItem
                  className="cursor-pointer rounded-md hover:bg-primary/10 hover:text-primary focus:bg-primary/10 focus:text-primary"
                  onSelect={() => router.push('/products?category=nuoc_uong')}
                >
                  <Droplets className="h-4 w-4 text-primary" />
                  {t('categoryWater')}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          <Link href="/track" className={navItemClass}>
            {t('track')}
          </Link>
          <Link href="/cam-nang" className={navItemClass}>
            {tNav('guide')}
          </Link>
          <a
            className="hidden items-center gap-2 rounded-md border border-slate-200 px-3 py-2 font-medium text-slate-700 transition hover:bg-slate-100 hover:text-slate-950 md:inline-flex"
            href={SHOP_INFO.hotline.href}
          >
            <Phone className="h-4 w-4" />
            {SHOP_INFO.hotline.label}
          </a>
          <LanguageSwitcher />
          <Button asChild size="icon" variant="ghost">
            <Link aria-label={t('cart')} className="relative" href="/cart">
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
