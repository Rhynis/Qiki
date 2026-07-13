import type { Metadata } from 'next'
import { useTranslations } from 'next-intl'
import { Suspense } from 'react'
import { LoginForm } from '@/components/auth/login-form'

export const metadata: Metadata = {
  title: 'Đăng nhập | Gas Quốc Cường',
}

export default function LoginPage() {
  const t = useTranslations('auth')
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">{t('loginTitle')}</h1>
      <Suspense fallback={null}>
        <LoginForm />
      </Suspense>
    </div>
  )
}
