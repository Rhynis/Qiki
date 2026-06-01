import { AlertTriangle, Phone } from 'lucide-react'

export function EmergencyBanner() {
  return (
    <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-900">
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
        <div className="space-y-1">
          <p className="font-semibold">Khẩn cấp an toàn gas</p>
          <p>Khóa van gas, mở cửa thông gió, không bật/tắt thiết bị điện.</p>
          <a className="inline-flex items-center gap-1 font-semibold" href="tel:0903026306">
            <Phone className="h-4 w-4" />
            090 3026306
          </a>
        </div>
      </div>
    </div>
  )
}
