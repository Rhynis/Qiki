'use client'

import { zodResolver } from '@hookform/resolvers/zod'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Button } from '@/components/ui/button'
import * as authApi from '@/lib/api/auth'
import {
  passwordHelpText,
  passwordResetRequestSchema,
  passwordResetSchema,
  type PasswordResetRequestValues,
  type PasswordResetValues,
} from '@/lib/validations/auth'

export function PasswordResetRequestForm() {
  const [formMessage, setFormMessage] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<PasswordResetRequestValues>({
    resolver: zodResolver(passwordResetRequestSchema),
    defaultValues: { email: '' },
    mode: 'onChange',
  })

  const onSubmit = async (values: PasswordResetRequestValues) => {
    setFormMessage(null)
    setFormError(null)
    try {
      await authApi.requestPasswordReset(values.email)
      setFormMessage('Nếu email tồn tại, hướng dẫn đặt lại mật khẩu đã được gửi.')
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : 'Không thể gửi hướng dẫn')
    }
  }

  return (
    <form className="space-y-5" onSubmit={handleSubmit(onSubmit)}>
      <div className="space-y-2">
        <label className="text-sm font-medium" htmlFor="email">
          Email
        </label>
        <input
          id="email"
          autoComplete="email"
          className="h-10 w-full rounded-md border px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
          {...register('email')}
        />
        {errors.email ? <p className="text-sm text-red-600">{errors.email.message}</p> : null}
      </div>
      {formMessage ? <p className="text-sm text-emerald-700">{formMessage}</p> : null}
      {formError ? <p className="text-sm text-red-600">{formError}</p> : null}
      <Button className="w-full" disabled={isSubmitting} type="submit">
        {isSubmitting ? 'Đang gửi...' : 'Gửi hướng dẫn'}
      </Button>
      <Link className="block text-center text-sm text-primary hover:underline" href="/login">
        Quay lại đăng nhập
      </Link>
    </form>
  )
}

export function PasswordResetConfirmForm() {
  const searchParams = useSearchParams()
  const [formMessage, setFormMessage] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<PasswordResetValues>({
    resolver: zodResolver(passwordResetSchema),
    defaultValues: {
      token: searchParams.get('token') ?? '',
      newPassword: '',
      confirmNewPassword: '',
    },
    mode: 'onChange',
  })

  const onSubmit = async (values: PasswordResetValues) => {
    setFormMessage(null)
    setFormError(null)
    try {
      await authApi.resetPassword(values.token ?? '', values.newPassword)
      setFormMessage('Mật khẩu đã được cập nhật. Vui lòng đăng nhập.')
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : 'Không thể cập nhật mật khẩu')
    }
  }

  return (
    <form className="space-y-5" onSubmit={handleSubmit(onSubmit)}>
      <input type="hidden" {...register('token')} />
      <div className="space-y-2">
        <label className="text-sm font-medium" htmlFor="newPassword">
          Mật khẩu mới
        </label>
        <input
          id="newPassword"
          type="password"
          autoComplete="new-password"
          className="h-10 w-full rounded-md border px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
          {...register('newPassword')}
        />
        <p className="text-xs text-slate-500">{passwordHelpText}</p>
        {errors.newPassword ? (
          <p className="text-sm text-red-600">{errors.newPassword.message}</p>
        ) : null}
      </div>
      <div className="space-y-2">
        <label className="text-sm font-medium" htmlFor="confirmNewPassword">
          Xác nhận mật khẩu mới
        </label>
        <input
          id="confirmNewPassword"
          type="password"
          autoComplete="new-password"
          className="h-10 w-full rounded-md border px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
          {...register('confirmNewPassword')}
        />
        {errors.confirmNewPassword ? (
          <p className="text-sm text-red-600">{errors.confirmNewPassword.message}</p>
        ) : null}
      </div>
      {formMessage ? <p className="text-sm text-emerald-700">{formMessage}</p> : null}
      {formError ? <p className="text-sm text-red-600">{formError}</p> : null}
      <Button className="w-full" disabled={isSubmitting} type="submit">
        {isSubmitting ? 'Đang cập nhật...' : 'Cập nhật mật khẩu'}
      </Button>
    </form>
  )
}
