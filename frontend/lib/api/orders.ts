import { apiClient } from '@/lib/api/client'
import type {
  CheckoutRequest,
  Delivery,
  DeliveryCreate,
  DeliveryStatusUpdate,
  GuestOrderLookup,
  Order,
  OrderCancelRequest,
  OrderListResponse,
  OrderSearchParams,
  OrderStatusUpdate,
} from '@/types/order'

export async function createOrder(data: CheckoutRequest, idempotencyKey: string): Promise<Order> {
  const response = await apiClient.post<Order>('/api/v1/orders/checkout', data, {
    headers: { 'Idempotency-Key': idempotencyKey },
  })
  return response.data
}

export async function lookupOrder(data: GuestOrderLookup): Promise<Order> {
  const response = await apiClient.post<Order>('/api/v1/orders/lookup', data)
  return response.data
}

export async function getMyOrders(params: OrderSearchParams = {}): Promise<OrderListResponse> {
  const response = await apiClient.get<OrderListResponse>('/api/v1/orders/me', { params })
  return response.data
}

export async function getOrder(orderId: string, phone?: string): Promise<Order> {
  const response = await apiClient.get<Order>(`/api/v1/orders/${orderId}`, {
    params: phone ? { phone } : undefined,
  })
  return response.data
}

export async function cancelOrder(orderId: string, data: OrderCancelRequest): Promise<Order> {
  const response = await apiClient.post<Order>(`/api/v1/orders/${orderId}/cancel`, data)
  return response.data
}

export async function getAdminOrders(params: OrderSearchParams = {}): Promise<OrderListResponse> {
  const response = await apiClient.get<OrderListResponse>('/api/v1/admin/orders', { params })
  return response.data
}

export async function updateOrderStatus(orderId: string, data: OrderStatusUpdate): Promise<Order> {
  const response = await apiClient.patch<Order>(`/api/v1/admin/orders/${orderId}/status`, data)
  return response.data
}

export async function createDelivery(orderId: string, data: DeliveryCreate): Promise<Delivery> {
  const response = await apiClient.post<Delivery>(
    `/api/v1/admin/orders/${orderId}/deliveries`,
    data
  )
  return response.data
}

export async function updateDeliveryStatus(
  orderId: string,
  deliveryId: string,
  data: DeliveryStatusUpdate
): Promise<Delivery> {
  const response = await apiClient.patch<Delivery>(
    `/api/v1/admin/orders/${orderId}/deliveries/${deliveryId}`,
    data
  )
  return response.data
}

export async function getOrderStatistics(): Promise<Record<string, number>> {
  const response = await apiClient.get<Record<string, number>>('/api/v1/admin/orders/statistics')
  return response.data
}
