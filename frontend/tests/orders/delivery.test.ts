import { describe, expect, it } from 'vitest'
import { allocatedByOrderItem, deliveryStatusTransitions } from '@/lib/utils/delivery'
import type { Delivery, Order } from '@/types/order'

function delivery(overrides: Partial<Delivery>): Delivery {
  return {
    id: 'd',
    order_id: 'o1',
    code: 'GB-1-D1',
    status: 'pending',
    scheduled_at: null,
    delivered_at: null,
    notes: null,
    items: [],
    created_at: '2026-07-12T00:00:00Z',
    ...overrides,
  }
}

function order(deliveries: Delivery[]): Order {
  return {
    id: 'o1',
    items: [{ id: 'i1' }, { id: 'i2' }],
    deliveries,
  } as unknown as Order
}

describe('delivery utils', () => {
  it('sums allocated quantities across non-cancelled deliveries', () => {
    const allocated = allocatedByOrderItem(
      order([
        delivery({ items: [{ id: 'x', delivery_id: 'd', order_item_id: 'i1', quantity: 2, created_at: '' }] }),
        delivery({
          status: 'cancelled',
          items: [{ id: 'y', delivery_id: 'd', order_item_id: 'i1', quantity: 5, created_at: '' }],
        }),
      ])
    )
    expect(allocated.i1).toBe(2) // cancelled delivery is ignored
    expect(allocated.i2).toBeUndefined()
  })

  it('exposes valid next statuses per current status', () => {
    expect(deliveryStatusTransitions.pending).toContain('shipping')
    expect(deliveryStatusTransitions.delivered).toEqual([])
  })
})
