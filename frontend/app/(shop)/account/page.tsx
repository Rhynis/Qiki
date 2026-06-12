'use client'

import { ClipboardList, KeyRound, Mail, Phone, ShieldCheck, UserRound } from 'lucide-react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { PageHeader } from '@/components/shared/page-header'
import { useAuth } from '@/lib/hooks/use-auth'

const roleLabels: Record<string, string> = {
  admin: 'Quản trị viên',
  staff: 'Nhân viên',
  customer: 'Khách hàng',
}

function displayValue(value: string | null | undefined) {
  return value?.trim() ? value : 'Chưa cập nhật'
}

export default function AccountPage() {
  const router = useRouter()
  const { user, isLoading, refreshUser } = useAuth()
  const [checked, setChecked] = useState(false)

  useEffect(() => {
    let mounted = true
    refreshUser()
      .then((currentUser) => {
        if (!currentUser) {
          router.replace('/login?redirectTo=/account')
        }
      })
      .finally(() => {
        if (mounted) setChecked(true)
      })
    return () => {
      mounted = false
    }
  }, [refreshUser, router])

  if (!checked || isLoading) {
    return (
      <section className="mx-auto max-w-4xl px-4 py-8">
        <div className="rounded-lg border bg-white p-6 text-sm text-slate-600">Đang tải...</div>
      </section>
    )
  }

  if (!user) return null

  const details = [
    {
      label: 'Họ tên',
      value: displayValue(user.full_name),
      icon: UserRound,
    },
    {
      label: 'Email',
      value: user.email,
      icon: Mail,
    },
    {
      label: 'Số điện thoại',
      value: displayValue(user.phone),
      icon: Phone,
    },
    {
      label: 'Vai trò',
      value: roleLabels[user.role] ?? user.role,
      icon: ShieldCheck,
    },
  ]

  return (
    <section className="mx-auto max-w-4xl space-y-6 px-4 py-8">
      <PageHeader title="Tài khoản" description="Thông tin đăng nhập và liên hệ của bạn." />

      <div className="rounded-lg border bg-white p-6 shadow-sm">
        <div className="grid gap-4 sm:grid-cols-2">
          {details.map((item) => {
            const Icon = item.icon
            return (
              <div key={item.label} className="rounded-lg border bg-slate-50 p-4">
                <div className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-600">
                  <Icon className="h-4 w-4 text-primary" />
                  {item.label}
                </div>
                <p className="break-words text-base font-semibold text-slate-950">{item.value}</p>
              </div>
            )
          })}
        </div>

        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          <Button asChild>
            <Link href="/forgot-password">
              <KeyRound className="mr-2 h-4 w-4" />
              Đổi mật khẩu
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link href="/orders">
              <ClipboardList className="mr-2 h-4 w-4" />
              Đơn hàng của tôi
            </Link>
          </Button>
        </div>
      </div>
    </section>
  )
}
