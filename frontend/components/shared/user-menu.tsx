'use client'

import Link from 'next/link'
import { useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/lib/hooks/use-auth'

export function UserMenu() {
  const { user, isAuthenticated, isAdmin, logout, refreshUser } = useAuth()

  useEffect(() => {
    if (!user) {
      void refreshUser()
    }
  }, [refreshUser, user])

  if (!isAuthenticated || !user) {
    return (
      <div className="flex items-center gap-1 sm:gap-2">
        <Button asChild size="sm" variant="ghost" className="px-2 sm:px-3">
          <Link href="/login">Đăng nhập</Link>
        </Button>
        <Button asChild size="sm" className="hidden px-2 sm:inline-flex sm:px-3">
          <Link href="/register">Đăng ký</Link>
        </Button>
      </div>
    )
  }

  const initial = (user.full_name ?? user.email ?? user.phone ?? '?').charAt(0).toUpperCase()

  return (
    <details className="relative">
      <summary className="flex cursor-pointer list-none items-center gap-2 rounded-md px-2 py-1.5 hover:bg-slate-100">
        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
          {initial}
        </span>
        <span className="hidden max-w-[140px] truncate text-sm sm:inline">
          {user.full_name ?? user.email}
        </span>
      </summary>
      <div className="absolute right-0 z-20 mt-2 w-56 rounded-md border bg-white p-1 text-sm shadow-lg">
        <Link className="block rounded px-3 py-2 hover:bg-slate-100" href="/account">
          Tài khoản
        </Link>
        <Link className="block rounded px-3 py-2 hover:bg-slate-100" href="/orders">
          Đơn hàng của tôi
        </Link>
        {isAdmin ? (
          <Link className="block rounded px-3 py-2 hover:bg-slate-100" href="/admin">
            Quản trị
          </Link>
        ) : null}
        <div className="my-1 border-t" />
        <button
          className="block w-full rounded px-3 py-2 text-left text-red-700 hover:bg-red-50"
          onClick={() => void logout()}
          type="button"
        >
          Đăng xuất
        </button>
      </div>
    </details>
  )
}
