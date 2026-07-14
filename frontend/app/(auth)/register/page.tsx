import type { Metadata } from 'next'
import { useTranslations } from 'next-intl'
import { RegisterForm } from '@/components/auth/register-form'

export const metadata: Metadata = {
  title: 'Đăng ký | Gas Quốc Cường',
}

export default function RegisterPage() {
  const t = useTranslations('auth')
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">{t('registerTitle')}</h1>
      <RegisterForm />
    </div>
  )
}
