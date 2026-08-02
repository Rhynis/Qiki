import type { Product } from '@/types/product'

/** The price actually charged: the sale price when it is a valid discount below list. */
export function effectivePriceValue(price: number, salePrice: number | null): number {
  return salePrice != null && salePrice > 0 && salePrice < price ? salePrice : price
}

/** Integer discount percentage when a valid sale price exists, else null. */
export function discountPercentValue(price: number, salePrice: number | null): number | null {
  if (salePrice == null || !(salePrice > 0 && salePrice < price)) return null
  return Math.round(((price - salePrice) / price) * 100)
}

type PricedProduct = Pick<Product, 'price' | 'sale_price'>

function toNumber(value: string | number | null): number | null {
  if (value == null) return null
  const parsed = typeof value === 'string' ? Number.parseFloat(value) : value
  return Number.isNaN(parsed) ? null : parsed
}

/** Effective price for a product (list price string + optional sale price string). */
export function effectivePrice(product: PricedProduct): number {
  return effectivePriceValue(Number(product.price), toNumber(product.sale_price))
}

/** Discount percentage for a product, or null when it is not on sale. */
export function discountPercent(product: PricedProduct): number | null {
  return discountPercentValue(Number(product.price), toNumber(product.sale_price))
}
