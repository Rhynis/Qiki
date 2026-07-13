'use client'

import { useTranslations } from 'next-intl'
import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Textarea } from '@/components/ui/textarea'
import { useCheckoutStore } from '@/lib/stores/checkout-store'
import { paymentSchema } from '@/lib/validations/order'
import type { PaymentMethod } from '@/types/order'

function issueMap(error: unknown): Record<string, string> {
  if (!error || typeof error !== 'object' || !('issues' in error)) return {}
  const issues = (error as { issues: Array<{ path: Array<string | number>; message: string }> })
    .issues
  return Object.fromEntries(issues.map((issue) => [issue.path.join('.'), issue.message]))
}

export function PaymentStep({ onNext }: { onNext: () => void }) {
  const t = useTranslations('checkout')
  const form = useCheckoutStore((state) => state.form)
  const updateForm = useCheckoutStore((state) => state.updateForm)
  const previousStep = useCheckoutStore((state) => state.previousStep)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const submit = () => {
    const result = paymentSchema.safeParse(form)
    if (!result.success) {
      setErrors(issueMap(result.error))
      return
    }
    setErrors({})
    onNext()
  }

  return (
    <div className="space-y-5 rounded-lg border bg-white p-5">
      <div className="space-y-3">
        <Label>{t('paymentMethod')}</Label>
        <RadioGroup
          className="grid gap-3 md:grid-cols-2"
          value={form.payment_method}
          onValueChange={(value) => updateForm({ payment_method: value as PaymentMethod })}
        >
          <label className="flex cursor-pointer items-center gap-3 rounded-lg border p-4">
            <RadioGroupItem value="cod" />
            <span>
              <span className="block font-medium">{t('codTitle')}</span>
              <span className="text-sm text-slate-600">{t('codDescription')}</span>
            </span>
          </label>
          <label className="flex cursor-pointer items-center gap-3 rounded-lg border p-4">
            <RadioGroupItem value="bank_transfer" />
            <span>
              <span className="block font-medium">{t('bankTransferTitle')}</span>
              <span className="text-sm text-slate-600">{t('bankTransferDescription')}</span>
            </span>
          </label>
        </RadioGroup>
        {errors.payment_method ? (
          <p className="text-sm text-red-700">{errors.payment_method}</p>
        ) : null}
      </div>

      <label className="flex items-center gap-2 text-sm font-medium">
        <Checkbox
          checked={form.vat_invoice_requested}
          onCheckedChange={(checked) => updateForm({ vat_invoice_requested: checked === true })}
        />
        {t('vatInvoice')}
      </label>

      {form.vat_invoice_requested ? (
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="company_name">{t('companyName')}</Label>
            <Input
              id="company_name"
              value={form.vat_info.company_name}
              onChange={(event) =>
                updateForm({ vat_info: { ...form.vat_info, company_name: event.target.value } })
              }
            />
            {errors['vat_info.company_name'] ? (
              <p className="text-sm text-red-700">{errors['vat_info.company_name']}</p>
            ) : null}
          </div>
          <div className="space-y-2">
            <Label htmlFor="tax_code">{t('taxCode')}</Label>
            <Input
              id="tax_code"
              value={form.vat_info.tax_code}
              onChange={(event) =>
                updateForm({ vat_info: { ...form.vat_info, tax_code: event.target.value } })
              }
            />
            {errors['vat_info.tax_code'] ? (
              <p className="text-sm text-red-700">{errors['vat_info.tax_code']}</p>
            ) : null}
          </div>
          <div className="space-y-2 md:col-span-2">
            <Label htmlFor="vat_address">{t('vatAddress')}</Label>
            <Input
              id="vat_address"
              value={form.vat_info.address}
              onChange={(event) =>
                updateForm({ vat_info: { ...form.vat_info, address: event.target.value } })
              }
            />
            {errors['vat_info.address'] ? (
              <p className="text-sm text-red-700">{errors['vat_info.address']}</p>
            ) : null}
          </div>
        </div>
      ) : null}

      <div className="space-y-2">
        <Label htmlFor="customer_notes">{t('orderNotes')}</Label>
        <Textarea
          id="customer_notes"
          value={form.customer_notes}
          onChange={(event) => updateForm({ customer_notes: event.target.value })}
        />
      </div>

      <div className="flex justify-between">
        <Button type="button" variant="outline" onClick={previousStep}>
          {t('back')}
        </Button>
        <Button type="button" onClick={submit}>
          {t('next')}
        </Button>
      </div>
    </div>
  )
}
