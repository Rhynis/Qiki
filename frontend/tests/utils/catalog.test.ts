import { describe, expect, it } from 'vitest'
import { groupWaterVariants } from '@/lib/utils/catalog'
import type { Product } from '@/types/product'

function makeProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: 'p1',
    sku: 'SKU-1',
    name: 'Product',
    brand: 'Brand',
    size_kg: '12.00',
    category: 'gas',
    unit: 'kg',
    price: '100000.00',
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
    ...overrides,
  }
}

describe('groupWaterVariants', () => {
  it('collapses water siblings sharing a parent into the cheapest representative', () => {
    const normal = makeProduct({
      id: 'w1',
      sku: 'VIHAWA-20L',
      category: 'nuoc_uong',
      parent_id: 'parent-vihawa',
      price: '55000.00',
    })
    const hotCold = makeProduct({
      id: 'w2',
      sku: 'VIHAWA-20L-NL',
      category: 'nuoc_uong',
      parent_id: 'parent-vihawa',
      price: '60000.00',
    })

    const result = groupWaterVariants([normal, hotCold])

    expect(result).toHaveLength(1)
    expect(result.map((p) => p.id)).toEqual(['w1'])
  })

  it('leaves every gas product individual even when they share a parent_id', () => {
    const twelve = makeProduct({
      id: 'g1',
      sku: 'ELF-12KG-DO',
      category: 'gas',
      parent_id: 'parent-elf',
    })
    const six = makeProduct({
      id: 'g2',
      sku: 'ELF-6KG-DO',
      category: 'gas',
      parent_id: 'parent-elf',
    })

    const result = groupWaterVariants([twelve, six])

    expect(result).toHaveLength(2)
    expect(result.map((p) => p.id).sort()).toEqual(['g1', 'g2'])
  })

  it('does not group a water product whose only sibling on this page is itself', () => {
    const solo = makeProduct({
      id: 'w1',
      sku: 'HOANHAO-20L',
      category: 'nuoc_uong',
      parent_id: 'parent-hoanhao',
    })

    const result = groupWaterVariants([solo])

    expect(result).toEqual([solo])
  })

  it('leaves an ungrouped water product (no parent_id) untouched', () => {
    const single = makeProduct({
      id: 'w1',
      sku: 'HOANHAO-20L',
      category: 'nuoc_uong',
      parent_id: null,
    })

    const result = groupWaterVariants([single])

    expect(result).toEqual([single])
  })
})
