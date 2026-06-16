'use client'

import { zodResolver } from '@hookform/resolvers/zod'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/lib/hooks/use-auth'
import { loginSchema, type LoginFormValues } from '@/lib/validations/auth'

function getSafeRedirectPath(value: string | null): string {
  if (!value || !value.startsWith('/') || value.startsWith('//') || value.includes('://')) {
    return '/'
  }
  return value
}

export function LoginForm() {
  const searchParams = useSearchParams()
  const { login, isLoading } = useAuth()
  const [submitError, setSubmitError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { identifier: '', password: '' },
    mode: 'onChange',
  })

  const onSubmit = async (values: LoginFormValues) => {
    setSubmitError(null)
    try {
      await login(
        values.identifier,
        values.password,
        getSafeRedirectPath(searchParams.get('redirectTo'))
      )
    } catch (caught) {
      setSubmitError(caught instanceof Error ? caught.message : 'Đăng nhập thất bại')
    }
  }

  return (
    <form className="space-y-5" onSubmit={handleSubmit(onSubmit)}>
      <div className="space-y-2">
        <label className="text-sm font-medium" htmlFor="identifier">
          Số điện thoại
        </label>
        <input
          id="identifier"
          autoComplete="username"
          className="h-10 w-full rounded-md border px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
          {...register('identifier')}
        />
        {errors.identifier ? (
          <p className="text-sm text-red-600">{errors.identifier.message}</p>
        ) : null}
      </div>

      <div className="space-y-2">
        <label className="text-sm font-medium" htmlFor="password">
          Mật khẩu
        </label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          className="h-10 w-full rounded-md border px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
          {...register('password')}
        />
        {errors.password ? <p className="text-sm text-red-600">{errors.password.message}</p> : null}
      </div>

      <div className="flex items-center justify-between text-sm">
        <Link className="text-primary hover:underline" href="/forgot-password">
          Quên mật khẩu?
        </Link>
        <Link className="text-primary hover:underline" href="/register">
          Đăng ký
        </Link>
      </div>

      {submitError ? <p className="text-center text-sm text-red-600">{submitError}</p> : null}
      <Button className="w-full" disabled={isLoading || isSubmitting} type="submit">
        {isLoading || isSubmitting ? 'Đang đăng nhập...' : 'Đăng nhập'}
      </Button>
    </form>
  )
}
