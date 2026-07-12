import type { Delivery, DeliveryStatus, Order } from '@/types/order'

export const deliveryStatusLabels: Record<DeliveryStatus, string> = {
  pending: 'Chờ giao',
  shipping: 'Đang giao',
  delivered: 'Đã giao',
  cancelled: 'Đã hủy',
}

/** Statuses a staff member can move a delivery to from its current status. */
export const deliveryStatusTransitions: Record<DeliveryStatus, DeliveryStatus[]> = {
  pending: ['shipping', 'delivered', 'cancelled'],
  shipping: ['delivered', 'cancelled'],
  delivered: [],
  cancelled: [],
}

/**
 * Quantity of each order item already committed to non-cancelled deliveries.
 * The server is authoritative; this only drives the admin UI's "remaining" hint.
 */
export function allocatedByOrderItem(order: Order): Record<string, number> {
  const allocated: Record<string, number> = {}
  for (const delivery of order.deliveries) {
    if (delivery.status === 'cancelled') continue
    for (const item of delivery.items) {
      allocated[item.order_item_id] = (allocated[item.order_item_id] ?? 0) + item.quantity
    }
  }
  return allocated
}

export function orderItemNameById(order: Order): Record<string, string> {
  return Object.fromEntries(order.items.map((item) => [item.id, item.product_name]))
}

export function deliveryItemLines(order: Order, delivery: Delivery): string[] {
  const names = orderItemNameById(order)
  return delivery.items.map(
    (item) => `${names[item.order_item_id] ?? 'Sản phẩm'} × ${item.quantity}`
  )
}
