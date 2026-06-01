import type { Metadata } from 'next'
import { Suspense } from 'react'
import { LoginForm } from '@/components/auth/login-form'

export const metadata: Metadata = {
  title: 'Đăng nhập | Gas Quốc Cường',
}

export default function LoginPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Đăng nhập</h1>
      <Suspense fallback={null}>
        <LoginForm />
      </Suspense>
    </div>
  )
}
