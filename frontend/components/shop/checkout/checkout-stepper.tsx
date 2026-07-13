'use client'

import { Check } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { cn } from '@/lib/utils'
import type { CheckoutStep } from '@/lib/stores/checkout-store'

const stepLabelKeys = {
  1: 'stepCart',
  2: 'stepInfo',
  3: 'stepPayment',
  4: 'stepConfirm',
} as const

export function CheckoutStepper({ step }: { step: CheckoutStep }) {
  const t = useTranslations('checkout')
  const steps: Array<{ id: CheckoutStep; label: string }> = [
    { id: 1, label: t(stepLabelKeys[1]) },
    { id: 2, label: t(stepLabelKeys[2]) },
    { id: 3, label: t(stepLabelKeys[3]) },
    { id: 4, label: t(stepLabelKeys[4]) },
  ]
  return (
    <div className="grid grid-cols-4 gap-2">
      {steps.map((item) => {
        const active = item.id === step
        const done = item.id < step
        return (
          <div key={item.id} className="flex min-w-0 items-center gap-2">
            <div
              className={cn(
                'flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-sm font-medium',
                active && 'border-primary bg-primary text-primary-foreground',
                done && 'border-emerald-600 bg-emerald-600 text-white',
                !active && !done && 'border-slate-300 bg-white text-slate-600'
              )}
            >
              {done ? <Check className="h-4 w-4" /> : item.id}
            </div>
            <span className={cn('truncate text-sm', active ? 'font-medium' : 'text-slate-600')}>
              {item.label}
            </span>
          </div>
        )
      })}
    </div>
  )
}
