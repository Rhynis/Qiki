import { beforeEach, describe, expect, it } from 'vitest'
import { useCartStore } from '@/lib/stores/cart-store'
import type { Product } from '@/types/product'

const product: Product = {
  id: '58f699da-9d92-4f09-b50c-334dded1de02',
  sku: 'GAS-12-SAIGON',
  name: 'Binh gas 12kg',
  brand: 'Saigon Petro',
  size_kg: '12.00',
  category: 'gas',
  unit: 'kg',
  price: '350000.00',
  sale_price: null,
  stock_quantity: 5,
  description: null,
  long_description: null,
  image_url: null,
  safety_info: null,
  pricing_note: null,
  is_active: true,
  created_at: '2026-05-29T00:00:00Z',
  updated_at: '2026-05-29T00:00:00Z',
  parent_id: null,
  colour: null,
  variant_label: null,
}

describe('cart store', () => {
  beforeEach(() => {
    useCartStore.getState().clearCart()
  })

  it('adds, updates, totals, and removes items', () => {
    useCartStore.getState().addItem(product, 2)
    useCartStore.getState().addItem(product, 1)

    expect(useCartStore.getState().getItemCount()).toBe(3)
    expect(useCartStore.getState().getTotal()).toBe(1050000)

    useCartStore.getState().updateQuantity(product.id, 1)
    expect(useCartStore.getState().getItemCount()).toBe(1)

    useCartStore.getState().removeItem(product.id)
    expect(useCartStore.getState().items).toHaveLength(0)
  })
})
