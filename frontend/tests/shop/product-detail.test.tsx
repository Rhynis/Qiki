import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ProductDetail } from '@/components/shop/product-detail'
import type { Product } from '@/types/product'
import { renderWithIntl as render } from '../i18n-render'

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => '/products/p1',
}))

vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }))

vi.mock('@/lib/hooks/use-wishlist', () => ({
  useWishlist: () => ({ savedIds: new Set<string>(), isAuthenticated: false }),
  useToggleWishlist: () => ({ mutate: vi.fn(), isPending: false }),
}))

function makeProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: 'p1',
    sku: 'GAS-12-SAIGON',
    name: 'Bình gas Saigon Petro 12kg',
    brand: 'Saigon Petro',
    size_kg: '12.00',
    category: 'gas',
    unit: 'kg',
    price: '605000.00',
    stock_quantity: 5,
    description: 'Short listing description',
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

describe('ProductDetail description', () => {
  it('renders the detailed (long) description when present', () => {
    render(
      <ProductDetail
        product={makeProduct({
          long_description: 'Detailed paragraph one.\n\nParagraph two with more info.',
        })}
      />
    )

    expect(screen.getByText(/Detailed paragraph one/)).toBeInTheDocument()
    expect(screen.getByText(/Paragraph two with more info/)).toBeInTheDocument()
    // The short listing text is not shown when a long description exists.
    expect(screen.queryByText('Short listing description')).not.toBeInTheDocument()
  })

  it('falls back to the short description when long_description is null', () => {
    render(<ProductDetail product={makeProduct({ long_description: null })} />)

    expect(screen.getByText('Short listing description')).toBeInTheDocument()
  })
})

describe('ProductDetail gas-safety notice', () => {
  it('renders the safety notice for a gas product with the shared hotline', () => {
    render(<ProductDetail product={makeProduct({ category: 'gas' })} />)

    const notice = screen.getByRole('note', { name: 'An toàn sử dụng gas' })
    expect(notice).toBeInTheDocument()
    expect(notice).toHaveTextContent('090 3026306')
    expect(notice).toHaveTextContent('114')
    expect(notice).toHaveTextContent('115')
  })

  it('does NOT render the safety notice for a water product', () => {
    render(
      <ProductDetail
        product={makeProduct({ category: 'nuoc_uong', unit: 'lít', size_kg: '20.00' })}
      />
    )

    expect(screen.queryByRole('note', { name: 'An toàn sử dụng gas' })).not.toBeInTheDocument()
  })
})
