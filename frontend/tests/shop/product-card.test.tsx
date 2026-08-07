import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ProductCard } from '@/components/shop/product-card'
import type { Product } from '@/types/product'
import { renderWithIntl as render } from '../i18n-render'

vi.mock('@/lib/hooks/use-wishlist', () => ({
  useWishlist: () => ({ savedIds: new Set<string>(), isAuthenticated: false }),
  useToggleWishlist: () => ({ mutate: vi.fn(), isPending: false }),
}))

function makeProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: 'p1',
    sku: 'SKU-1',
    name: 'Product',
    brand: 'Brand',
    size_kg: '12.00',
    category: 'gas',
    unit: 'kg',
    price: '605000.00',
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

describe('ProductCard grouping hint', () => {
  it('does NOT show the "Từ / Nhiều lựa chọn" hint for a gas product, even with a parent_id', () => {
    // Gas products still carry a parent_id (brand grouping in the DB), but the
    // listing shows every gas SKU individually (#342) — the hint is water-only.
    render(<ProductCard product={makeProduct({ category: 'gas', parent_id: 'parent-elf' })} />)

    expect(screen.queryByText('Từ')).not.toBeInTheDocument()
    expect(screen.queryByText(/Nhiều lựa chọn/)).not.toBeInTheDocument()
  })

  it('shows the "Từ / Nhiều lựa chọn" hint for a grouped water product', () => {
    render(
      <ProductCard
        product={makeProduct({ category: 'nuoc_uong', unit: 'lít', parent_id: 'parent-vihawa' })}
      />
    )

    expect(screen.getByText('Từ')).toBeInTheDocument()
    expect(screen.getByText(/Nhiều lựa chọn/)).toBeInTheDocument()
  })

  it('does not show the hint for an ungrouped water product (no parent_id)', () => {
    render(
      <ProductCard product={makeProduct({ category: 'nuoc_uong', unit: 'lít', parent_id: null })} />
    )

    expect(screen.queryByText('Từ')).not.toBeInTheDocument()
    expect(screen.queryByText(/Nhiều lựa chọn/)).not.toBeInTheDocument()
  })
})
