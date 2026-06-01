import type { Metadata } from 'next'
import { RegisterForm } from '@/components/auth/register-form'

export const metadata: Metadata = {
  title: 'Đăng ký | Gas Quốc Cường',
}

export default function RegisterPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Đăng ký</h1>
      <RegisterForm />
    </div>
  )
}
