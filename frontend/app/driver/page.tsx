'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { MapPin, Phone } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { PageHeader } from '@/components/shared/page-header'
import { Button } from '@/components/ui/button'
import {
  getDriverDeliveries,
  updateDriverDeliveryStatus,
  type DriverDelivery,
  type DriverStatusUpdate,
} from '@/lib/api/driver'
import { useAuth } from '@/lib/hooks/use-auth'

const STATUS_LABELS: Record<string, string> = {
  pending: 'Chờ giao',
  shipping: 'Đang giao',
  delivered: 'Đã giao',
  failed: 'Giao thất bại',
  cancelled: 'Đã hủy',
}

async function readLocation(): Promise<{ lat: number; lng: number } | null> {
  if (typeof navigator === 'undefined' || !navigator.geolocation) return null
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (position) => resolve({ lat: position.coords.latitude, lng: position.coords.longitude }),
      () => resolve(null),
      { timeout: 8000 }
    )
  })
}

function DeliveryCard({ delivery }: { delivery: DriverDelivery }) {
  const queryClient = useQueryClient()
  const [shareLocation, setShareLocation] = useState(false)
  const mutation = useMutation({
    mutationFn: (data: DriverStatusUpdate) => updateDriverDeliveryStatus(delivery.id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['driver-deliveries'] })
      toast.success('Đã cập nhật trạng thái giao hàng.')
    },
    onError: (error) =>
      toast.error(error instanceof Error ? error.message : 'Không thể cập nhật trạng thái.'),
  })

  const isDone = delivery.status === 'delivered' || delivery.status === 'failed'

  const submit = async (status: 'delivered' | 'failed') => {
    const location = shareLocation ? await readLocation() : null
    mutation.mutate({ status, lat: location?.lat ?? null, lng: location?.lng ?? null })
  }

  return (
    <div className="rounded-lg border bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-medium">{delivery.code}</p>
          <p className="text-sm text-slate-600">{delivery.customer_name}</p>
        </div>
        <span className="shrink-0 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium">
          {STATUS_LABELS[delivery.status] ?? delivery.status}
        </span>
      </div>

      <div className="mt-3 space-y-1 text-sm text-slate-700">
        <p className="flex items-start gap-2">
          <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
          {delivery.delivery_address}
        </p>
        <a
          className="flex items-center gap-2 hover:text-primary"
          href={`tel:${delivery.customer_phone}`}
        >
          <Phone className="h-4 w-4 shrink-0 text-primary" />
          {delivery.customer_phone}
        </a>
      </div>

      <ul className="mt-3 space-y-1 text-sm">
        {delivery.items.map((item, index) => (
          <li key={`${item.product_name}-${index}`} className="flex justify-between">
            <span className="min-w-0 truncate">{item.product_name}</span>
            <span className="shrink-0 text-slate-600">x{item.quantity}</span>
          </li>
        ))}
      </ul>

      {isDone ? null : (
        <div className="mt-4 space-y-3 border-t pt-3">
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-input text-primary focus:ring-ring"
              checked={shareLocation}
              onChange={(event) => setShareLocation(event.target.checked)}
            />
            Chia sẻ vị trí của tôi khi cập nhật (không bắt buộc)
          </label>
          <div className="flex gap-2">
            <Button
              className="flex-1"
              disabled={mutation.isPending}
              onClick={() => void submit('delivered')}
            >
              Đã giao
            </Button>
            <Button
              className="flex-1"
              variant="outline"
              disabled={mutation.isPending}
              onClick={() => void submit('failed')}
            >
              Giao thất bại
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

export default function DriverPage() {
  const { isDriver, isLoading: authLoading } = useAuth()
  const { data, isLoading, isError } = useQuery({
    queryKey: ['driver-deliveries'],
    queryFn: getDriverDeliveries,
    enabled: isDriver,
  })

  if (authLoading) {
    return <p className="p-6 text-sm text-slate-600">Đang tải...</p>
  }
  if (!isDriver) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center">
        <p className="text-slate-700">Khu vực này chỉ dành cho tài xế giao hàng.</p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 px-4 py-8">
      <PageHeader title="Giao hàng của tôi" description="Các đơn được phân cho bạn." />
      {isLoading ? <p className="text-sm text-slate-600">Đang tải đơn giao...</p> : null}
      {isError ? <p className="text-sm text-red-700">Không thể tải danh sách giao hàng.</p> : null}
      {data && data.length === 0 ? (
        <p className="rounded-lg border bg-white p-6 text-center text-slate-600">
          Hiện chưa có đơn giao nào được phân cho bạn.
        </p>
      ) : null}
      <div className="space-y-3">
        {data?.map((delivery) => (
          <DeliveryCard key={delivery.id} delivery={delivery} />
        ))}
      </div>
    </div>
  )
}
