import type { Metadata } from 'next'
import { PriceAlertSubscribeForm } from '@/components/price-alerts/subscribe-form'

export const metadata: Metadata = {
  title: 'Đăng ký nhận giá gas | Gas Quốc Cường',
  description: 'Nhận email thông báo mỗi khi Gas Quốc Cường cập nhật giá gas.',
}

export default function PriceAlertsPage() {
  return (
    <div className="mx-auto max-w-md space-y-6 px-4 py-10">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">Đăng ký nhận giá gas</h1>
        <p className="text-sm text-slate-600">
          Giá gas thường thay đổi hằng tháng. Để lại email để Gas Quốc Cường gửi bảng giá mới ngay
          khi có cập nhật. Bạn sẽ nhận một email xác nhận trước khi đăng ký hoàn tất.
        </p>
      </div>
      <PriceAlertSubscribeForm />
    </div>
  )
}
