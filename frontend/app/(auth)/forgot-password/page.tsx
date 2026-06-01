import type { Metadata } from 'next'
import { PasswordResetRequestForm } from '@/components/auth/password-reset-form'

export const metadata: Metadata = {
  title: 'Quên mật khẩu | Gas Quốc Cường',
}

export default function ForgotPasswordPage() {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">Quên mật khẩu</h1>
        <p className="text-sm text-slate-600">Nhập email để nhận hướng dẫn đặt lại mật khẩu.</p>
      </div>
      <PasswordResetRequestForm />
    </div>
  )
}
