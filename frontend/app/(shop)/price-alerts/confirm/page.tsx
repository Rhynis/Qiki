import type { Metadata } from 'next'
import { Suspense } from 'react'
import { TokenActionClient } from '@/components/price-alerts/token-action-client'

export const metadata: Metadata = {
  title: 'Xác nhận nhận giá gas | Gas Quốc Cường',
}

export default function ConfirmPriceAlertsPage() {
  return (
    <div className="mx-auto max-w-md space-y-6 px-4 py-10">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">Xác nhận đăng ký</h1>
        <p className="text-sm text-slate-600">
          Nhấn nút bên dưới để xác nhận đăng ký nhận email thông báo giá gas.
        </p>
      </div>
      <Suspense fallback={null}>
        <TokenActionClient variant="confirm" />
      </Suspense>
    </div>
  )
}
