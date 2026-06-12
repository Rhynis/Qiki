'use client'

import { zodResolver } from '@hookform/resolvers/zod'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import * as authApi from '@/lib/api/auth'
import {
  passwordResetRequestSchema,
  passwordResetSchema,
  type PasswordResetRequestValues,
  type PasswordResetValues,
} from '@/lib/validations/auth'

export function PasswordResetRequestForm() {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<PasswordResetRequestValues>({
    resolver: zodResolver(passwordResetRequestSchema),
    defaultValues: { email: '' },
  })

  const onSubmit = async (values: PasswordResetRequestValues) => {
    await authApi.requestPasswordReset(values.email)
    toast.success('Nếu email tồn tại, hướng dẫn đặt lại mật khẩu đã được gửi.')
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
  })

  const onSubmit = async (values: PasswordResetValues) => {
    await authApi.resetPassword(values.token ?? '', values.newPassword)
    toast.success('Mật khẩu đã được cập nhật. Vui lòng đăng nhập.')
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
        <p className="text-xs text-slate-500">Mật khẩu tối thiểu 8 ký tự</p>
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
      <Button className="w-full" disabled={isSubmitting} type="submit">
        {isSubmitting ? 'Đang cập nhật...' : 'Cập nhật mật khẩu'}
      </Button>
    </form>
  )
}
