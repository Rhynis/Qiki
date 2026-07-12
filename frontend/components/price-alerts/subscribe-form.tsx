'use client'

import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Button } from '@/components/ui/button'
import * as priceAlertsApi from '@/lib/api/price-alerts'
import {
  priceAlertSubscribeSchema,
  type PriceAlertSubscribeValues,
} from '@/lib/validations/price-alerts'

export function PriceAlertSubscribeForm() {
  const [formMessage, setFormMessage] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<PriceAlertSubscribeValues>({
    resolver: zodResolver(priceAlertSubscribeSchema),
    defaultValues: { email: '', consent: true },
    mode: 'onChange',
  })

  const onSubmit = async (values: PriceAlertSubscribeValues) => {
    setFormMessage(null)
    setFormError(null)
    try {
      const result = await priceAlertsApi.subscribePriceAlerts(values.email, values.consent)
      setFormMessage(result.message)
      reset({ email: '', consent: true })
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : 'Không thể đăng ký, vui lòng thử lại')
    }
  }

  return (
    <form className="space-y-5" onSubmit={handleSubmit(onSubmit)}>
      <div className="space-y-2">
        <label className="text-sm font-medium" htmlFor="email">
          Email nhận thông báo giá
        </label>
        <input
          id="email"
          autoComplete="email"
          className="h-10 w-full rounded-md border px-3 text-sm outline-none focus:ring-2 focus:ring-ring"
          placeholder="ten@gmail.com"
          {...register('email')}
        />
        {errors.email ? <p className="text-sm text-red-600">{errors.email.message}</p> : null}
      </div>
      <div className="flex items-start gap-2">
        <input
          id="consent"
          type="checkbox"
          className="mt-1 h-4 w-4 rounded border-input text-primary focus:ring-ring"
          {...register('consent')}
        />
        <label className="text-sm text-slate-600" htmlFor="consent">
          Tôi đồng ý nhận email thông báo khi Gas Quốc Cường thay đổi giá gas. Bạn có thể hủy đăng
          ký bất cứ lúc nào.
        </label>
      </div>
      {errors.consent ? <p className="text-sm text-red-600">{errors.consent.message}</p> : null}
      {formMessage ? <p className="text-sm text-emerald-700">{formMessage}</p> : null}
      {formError ? <p className="text-sm text-red-600">{formError}</p> : null}
      <Button className="w-full" disabled={isSubmitting} type="submit">
        {isSubmitting ? 'Đang gửi...' : 'Đăng ký nhận giá'}
      </Button>
    </form>
  )
}
