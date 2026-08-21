import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { RecommendedProducts } from '@/components/shop/recommended-products'
import type { RecommendedProduct } from '@/types/product'
import { renderWithIntl } from '../i18n-render'

vi.mock('@/lib/hooks/use-wishlist', () => ({
  useWishlist: () => ({ savedIds: new Set<string>(), isAuthenticated: false }),
  useToggleWishlist: () => ({ mutate: vi.fn(), isPending: false }),
}))

const useRecommendedProductsMock = vi.fn()
vi.mock('@/lib/hooks/use-recommendations', () => ({
  useRecommendedProducts: (...args: unknown[]) => useRecommendedProductsMock(...args),
}))

function makeRecommendation(overrides: Partial<RecommendedProduct> = {}): RecommendedProduct {
  return {
    id: 'r1',
    sku: 'SKU-R1',
    name: 'Nước Vihawa 20 lít',
    brand: 'Vihawa',
    size_kg: '20.00',
    category: 'nuoc_uong',
    unit: 'lít',
    price: '55000.00',
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
    score: 0.4,
    reason: 'Khách mua gas thường lấy kèm nước uống',
    ...overrides,
  }
}

describe('RecommendedProducts loading state', () => {
  it('renders skeleton placeholders, not the title, while loading', () => {
    useRecommendedProductsMock.mockReturnValue({ data: undefined, isLoading: true })

    const { container } = renderWithIntl(<RecommendedProducts productId="p1" />)

    expect(screen.queryByText('Gợi ý cho bạn')).not.toBeInTheDocument()
    expect(container.querySelectorAll('.animate-pulse').length).toBeGreaterThan(0)
  })
})

describe('RecommendedProducts empty state', () => {
  it('renders nothing when there are no recommendations', () => {
    useRecommendedProductsMock.mockReturnValue({ data: [], isLoading: false })

    const { container } = renderWithIntl(<RecommendedProducts productId="p1" />)

    expect(container).toBeEmptyDOMElement()
  })
})

describe('RecommendedProducts with data', () => {
  it('renders each product with its catalog-derived reason', () => {
    useRecommendedProductsMock.mockReturnValue({
      data: [makeRecommendation()],
      isLoading: false,
    })

    renderWithIntl(<RecommendedProducts productId="p1" />)

    expect(screen.getByText('Gợi ý cho bạn')).toBeInTheDocument()
    expect(screen.getByText('Nước Vihawa 20 lít')).toBeInTheDocument()
    expect(screen.getByText('Khách mua gas thường lấy kèm nước uống')).toBeInTheDocument()
  })

  it('shows the English title under the en locale (Vietnamese reason unchanged)', () => {
    useRecommendedProductsMock.mockReturnValue({
      data: [makeRecommendation()],
      isLoading: false,
    })

    renderWithIntl(<RecommendedProducts productId="p1" />, { locale: 'en' })

    expect(screen.getByText('Recommended for you')).toBeInTheDocument()
    // The reason string is backend-sourced Vietnamese regardless of UI locale.
    expect(screen.getByText('Khách mua gas thường lấy kèm nước uống')).toBeInTheDocument()
  })
})
