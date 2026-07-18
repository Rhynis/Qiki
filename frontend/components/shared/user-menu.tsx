'use client'

import Link from 'next/link'
import { useTranslations } from 'next-intl'
import { useEffect, useRef, useState } from 'react'
import { useAuth } from '@/lib/hooks/use-auth'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Button } from '@/components/ui/button'

export function UserMenu() {
  const t = useTranslations('userMenu')
  const { user, isAuthenticated, isAdmin, logout, refreshUser } = useAuth()
  const [open, setOpen] = useState(false)
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!user) {
      void refreshUser()
    }
  }, [refreshUser, user])

  useEffect(() => {
    return () => {
      if (closeTimerRef.current) clearTimeout(closeTimerRef.current)
    }
  }, [])

  function openMenu() {
    if (closeTimerRef.current) {
      clearTimeout(closeTimerRef.current)
      closeTimerRef.current = null
    }
    setOpen(true)
  }

  function scheduleMenuClose() {
    if (closeTimerRef.current) clearTimeout(closeTimerRef.current)
    closeTimerRef.current = setTimeout(() => {
      setOpen(false)
      closeTimerRef.current = null
    }, 150)
  }

  if (!isAuthenticated || !user) {
    return (
      <div className="flex items-center gap-1 sm:gap-2">
        <Button asChild size="sm" variant="ghost" className="px-2 sm:px-3">
          <Link href="/login">{t('login')}</Link>
        </Button>
        <Button asChild size="sm" className="hidden px-2 sm:inline-flex sm:px-3">
          <Link href="/register">{t('register')}</Link>
        </Button>
      </div>
    )
  }

  const initial = (user.full_name ?? user.email ?? user.phone ?? '?').charAt(0).toUpperCase()
  const displayName = user.full_name ?? user.email ?? t('fallbackName')

  return (
    <div className="relative" onMouseEnter={openMenu} onMouseLeave={scheduleMenuClose}>
      <DropdownMenu modal={false} open={open} onOpenChange={setOpen}>
        <DropdownMenuTrigger asChild>
          {/* Clicking the name/avatar goes straight to /account; the dropdown
              still opens on hover (wrapper) and on keyboard Enter (Radix). */}
          <Link
            aria-label={displayName}
            href="/account"
            className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            onClick={() => setOpen(false)}
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
              {initial}
            </span>
            <span className="hidden max-w-[140px] truncate text-sm sm:inline">{displayName}</span>
          </Link>
        </DropdownMenuTrigger>
        <DropdownMenuContent
          align="end"
          className="w-56"
          onMouseEnter={openMenu}
          onMouseLeave={scheduleMenuClose}
        >
          <DropdownMenuItem asChild>
            <Link href="/account">{t('account')}</Link>
          </DropdownMenuItem>
          <DropdownMenuItem asChild>
            <Link href="/orders">{t('myOrders')}</Link>
          </DropdownMenuItem>
          <DropdownMenuItem asChild>
            <Link href="/wishlist">{t('wishlist')}</Link>
          </DropdownMenuItem>
          {isAdmin ? (
            <DropdownMenuItem asChild>
              <Link href="/admin">{t('admin')}</Link>
            </DropdownMenuItem>
          ) : null}
          <DropdownMenuSeparator />
          <DropdownMenuItem
            className="cursor-pointer text-red-700 focus:bg-red-50 focus:text-red-700"
            onSelect={() => void logout()}
          >
            {t('logout')}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}
