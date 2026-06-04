import { describe, expect, it } from 'vitest'
import { productFiltersSchema, productSchema } from '@/lib/validations/product'

describe('productSchema', () => {
  it('normalizes sku and validates allowed size', () => {
    const result = productSchema.parse({
      sku: 'gas-12-saigon',
      name: 'Binh gas 12kg',
      brand: 'Saigon Petro',
      size_kg: '12',
      price: '350000',
      stock_quantity: '5',
    })

    expect(result.sku).toBe('GAS-12-SAIGON')
    expect(result.stock_quantity).toBe(5)
  })

  it('rejects unsupported cylinder size', () => {
    const result = productSchema.safeParse({
      sku: 'GAS-10',
      name: 'Binh gas 10kg',
      brand: 'Saigon Petro',
      size_kg: '10',
      price: '350000',
      stock_quantity: 5,
    })

    expect(result.success).toBe(false)
  })

  it('accepts water products with 20 liter size', () => {
    const result = productSchema.parse({
      sku: 'vihawa-20l',
      name: 'Nuoc Vihawa 20 lit',
      brand: 'Vihawa',
      category: 'nuoc_uong',
      unit: 'lít',
      size_kg: '20',
      price: '50000',
      stock_quantity: 50,
      pricing_note: 'Giao hang tinh them phi.',
    })

    expect(result.sku).toBe('VIHAWA-20L')
    expect(result.size_kg).toBe('20')
  })
})

describe('productFiltersSchema', () => {
  it('rejects inverted price ranges', () => {
    const result = productFiltersSchema.safeParse({
      min_price: '400000',
      max_price: '300000',
    })

    expect(result.success).toBe(false)
  })
})
