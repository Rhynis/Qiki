import type { Metadata } from 'next'
import { useTranslations } from 'next-intl'
import { PasswordResetRequestForm } from '@/components/auth/password-reset-form'

export const metadata: Metadata = {
  title: 'Quên mật khẩu | Gas Quốc Cường',
}

export default function ForgotPasswordPage() {
  const t = useTranslations('auth')
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">{t('forgotTitle')}</h1>
        <p className="text-sm text-slate-600">{t('forgotSubtitle')}</p>
      </div>
      <PasswordResetRequestForm />
    </div>
  )
}
