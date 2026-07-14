'use client'

import { CheckCircle2, Circle } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { cn } from '@/lib/utils'
import type { OrderStatus } from '@/types/order'

const stepStatuses = ['pending', 'confirmed', 'shipping', 'delivered'] as const

export function OrderStatusTimeline({ status }: { status: OrderStatus }) {
  const t = useTranslations('orderTimeline')
  const steps = stepStatuses.map((stepStatus) => ({
    status: stepStatus,
    label: t(stepStatus),
  }))

  if (status === 'cancelled') {
    return (
      <p className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
        {t('cancelledNotice')}
      </p>
    )
  }
  const currentIndex = steps.findIndex((step) => step.status === status)
  return (
    <div className="grid gap-3 sm:grid-cols-4">
      {steps.map((step, index) => {
        const complete = index <= currentIndex
        return (
          <div key={step.status} className="flex items-center gap-2">
            {complete ? (
              <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            ) : (
              <Circle className="h-5 w-5 text-slate-300" />
            )}
            <span className={cn('text-sm', complete ? 'font-medium' : 'text-slate-500')}>
              {step.label}
            </span>
          </div>
        )
      })}
    </div>
  )
}
