'use client'

import {
  BarChart3,
  BookOpenText,
  ClipboardList,
  LayoutDashboard,
  LifeBuoy,
  MessageSquareText,
  Package,
  Users,
} from 'lucide-react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useEffect, useState, type ReactNode } from 'react'
import { cn } from '@/lib/utils'
import { useAuth } from '@/lib/hooks/use-auth'

type AdminLayoutProps = {
  children: ReactNode
}

const navItems = [
  { href: '/admin', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/admin/products', label: 'Sản phẩm', icon: Package },
  { href: '/admin/orders', label: 'Đơn hàng', icon: ClipboardList },
  { href: '/admin/chat', label: 'Chat', icon: MessageSquareText },
  { href: '/admin/insights', label: 'Thống kê', icon: BarChart3 },
  { href: '/admin/knowledge-base', label: 'Knowledge Base', icon: BookOpenText },
  { href: '/admin/users', label: 'Người dùng', icon: Users },
  { href: '/admin/guide', label: 'Cẩm nang', icon: LifeBuoy },
]

export default function AdminLayout({ children }: AdminLayoutProps) {
  const pathname = usePathname()
  const router = useRouter()
  const { isAdmin, isLoading, refreshUser } = useAuth()
  const [checked, setChecked] = useState(false)

  useEffect(() => {
    let mounted = true
    refreshUser().finally(() => {
      if (mounted) setChecked(true)
    })
    return () => {
      mounted = false
    }
  }, [refreshUser])

  useEffect(() => {
    if (checked && !isLoading && !isAdmin) {
      router.replace('/')
    }
  }, [checked, isAdmin, isLoading, router])

  if (!checked || isLoading) {
    return (
      <section className="mx-auto max-w-6xl px-4 py-8">
        <div className="rounded-lg border bg-white p-6 text-sm text-slate-600">Đang tải...</div>
      </section>
    )
  }

  if (!isAdmin) return null

  return (
    <div className="mx-auto flex max-w-7xl gap-6 px-4 py-6">
      <aside className="hidden w-56 shrink-0 md:block">
        <nav className="sticky top-20 space-y-1 rounded-lg border bg-white p-2">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive =
              pathname === item.href || (item.href !== '/admin' && pathname.startsWith(item.href))
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  'flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100',
                  isActive && 'bg-slate-900 text-white hover:bg-slate-900'
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            )
          })}
        </nav>
      </aside>
      <div className="min-w-0 flex-1">
        <div className="mb-4 flex gap-2 overflow-x-auto md:hidden">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive =
              pathname === item.href || (item.href !== '/admin' && pathname.startsWith(item.href))
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  'flex shrink-0 items-center gap-2 rounded-md border bg-white px-3 py-2 text-sm font-medium text-slate-700',
                  isActive && 'border-slate-900 bg-slate-900 text-white'
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
            )
          })}
        </div>
        {children}
      </div>
    </div>
  )
}
