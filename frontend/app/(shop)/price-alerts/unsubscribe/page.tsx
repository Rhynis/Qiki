import type { Metadata } from 'next'
import { Suspense } from 'react'
import { TokenActionClient } from '@/components/price-alerts/token-action-client'

export const metadata: Metadata = {
  title: 'Hủy nhận giá gas | Gas Quốc Cường',
}

export default function UnsubscribePriceAlertsPage() {
  return (
    <div className="mx-auto max-w-md space-y-6 px-4 py-10">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">Hủy nhận thông báo giá</h1>
        <p className="text-sm text-slate-600">
          Nhấn nút bên dưới để ngừng nhận email thông báo giá gas từ Gas Quốc Cường.
        </p>
      </div>
      <Suspense fallback={null}>
        <TokenActionClient variant="unsubscribe" />
      </Suspense>
    </div>
  )
}
