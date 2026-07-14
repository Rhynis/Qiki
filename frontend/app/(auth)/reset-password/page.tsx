import type { Metadata } from 'next'
import { useTranslations } from 'next-intl'
import { Suspense } from 'react'
import { PasswordResetConfirmForm } from '@/components/auth/password-reset-form'

export const metadata: Metadata = {
  title: 'Đặt lại mật khẩu | Gas Quốc Cường',
}

export default function ResetPasswordPage() {
  const t = useTranslations('auth')
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">{t('resetTitle')}</h1>
      <Suspense fallback={null}>
        <PasswordResetConfirmForm />
      </Suspense>
    </div>
  )
}
