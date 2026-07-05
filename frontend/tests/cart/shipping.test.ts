import { describe, expect, it } from 'vitest'
import { calculateCartShipping, type CartItem } from '@/lib/stores/cart-store'

function item(overrides: Partial<CartItem>): CartItem {
  return {
    productId: overrides.productId ?? 'p1',
    name: 'Item',
    brand: 'Brand',
    sizeKg: 12,
    unit: 'kg',
    price: 100000,
    quantity: 1,
    ...overrides,
  }
}

describe('calculateCartShipping', () => {
  it('is 0 for an empty cart', () => {
    expect(calculateCartShipping([])).toBe(0)
  })

  it('ships gas for free', () => {
    expect(calculateCartShipping([item({ category: 'gas', quantity: 3 })])).toBe(0)
  })

  it('charges 5.000đ per water unit, mirroring the server', () => {
    expect(calculateCartShipping([item({ category: 'nuoc_uong', quantity: 2 })])).toBe(10000)
  })

  it('charges only for the water units in a mixed cart', () => {
    const shipping = calculateCartShipping([
      item({ productId: 'gas', category: 'gas', quantity: 2 }),
      item({ productId: 'water', category: 'nuoc_uong', quantity: 1 }),
    ])
    expect(shipping).toBe(5000)
  })
})
