import { apiClient } from '@/lib/api/client'

export type DriverDeliveryStatus =
  | 'pending'
  | 'shipping'
  | 'delivered'
  | 'failed'
  | 'cancelled'

export interface DriverDeliveryLine {
  product_name: string
  quantity: number
}

export interface DriverDelivery {
  id: string
  code: string
  status: DriverDeliveryStatus
  customer_name: string
  customer_phone: string
  delivery_address: string
  notes: string | null
  scheduled_at: string | null
  delivered_at: string | null
  last_lat: number | null
  last_lng: number | null
  items: DriverDeliveryLine[]
  created_at: string
}

export interface DriverStatusUpdate {
  status: 'delivered' | 'failed'
  notes?: string | null
  lat?: number | null
  lng?: number | null
}

export async function getDriverDeliveries(): Promise<DriverDelivery[]> {
  const response = await apiClient.get<DriverDelivery[]>('/api/v1/driver/deliveries')
  return response.data
}

export async function updateDriverDeliveryStatus(
  deliveryId: string,
  data: DriverStatusUpdate
): Promise<DriverDelivery> {
  const response = await apiClient.patch<DriverDelivery>(
    `/api/v1/driver/deliveries/${deliveryId}/status`,
    data
  )
  return response.data
}
