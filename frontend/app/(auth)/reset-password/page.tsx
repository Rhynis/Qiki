import type { Metadata } from 'next'
import { Suspense } from 'react'
import { PasswordResetConfirmForm } from '@/components/auth/password-reset-form'

export const metadata: Metadata = {
  title: 'Đặt lại mật khẩu | Gas Quốc Cường',
}

export default function ResetPasswordPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Đặt lại mật khẩu</h1>
      <Suspense fallback={null}>
        <PasswordResetConfirmForm />
      </Suspense>
    </div>
  )
}
