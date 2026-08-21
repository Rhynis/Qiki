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

vi.mock('@/lib/hooks/use-recommendations', () => ({
  useRecommendedProducts: () => ({ data: [], isLoading: false }),
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
    sale_price: null,
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

  it('shows exactly one safety section for a gas product even when safety_info is set', () => {
    render(
      <ProductDetail
        product={makeProduct({
          category: 'gas',
          safety_info: 'An toàn sử dụng — Không tự ý sửa van.',
        })}
      />
    )

    // The GasSafetyNotice is the single safety block; the legacy safety_info card
    // (which duplicated it on gas pages) has been removed.
    expect(screen.getAllByRole('note', { name: 'An toàn sử dụng gas' })).toHaveLength(1)
    expect(screen.queryByText('An toàn sử dụng — Không tự ý sửa van.')).not.toBeInTheDocument()
  })
})

describe('ProductDetail variant selector', () => {
  it('renders the variant selector for a water product with multiple variants', () => {
    const normal = makeProduct({
      id: 'w1',
      sku: 'VIHAWA-20L',
      name: 'Nước Vihawa 20 lít',
      brand: 'Vihawa',
      category: 'nuoc_uong',
      unit: 'lít',
      size_kg: '20.00',
      variant_label: 'Bình thường',
    })
    const hotCold = makeProduct({
      ...normal,
      id: 'w2',
      sku: 'VIHAWA-20L-NL',
      name: 'Nước Vihawa 20 lít (bình nóng lạnh)',
      variant_label: 'Bình nóng lạnh',
    })

    render(<ProductDetail product={normal} variants={[normal, hotCold]} />)

    expect(screen.getByRole('radiogroup')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /Bình thường/ })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /Bình nóng lạnh/ })).toBeInTheDocument()
  })

  it('does NOT render the selector for gas even when sibling variants are passed', () => {
    // Gas varies by size (6/12/45 kg); grouping it under a selector let the page
    // title (fixed to the originally loaded product) drift from the selected
    // size (#342) — e.g. a "12kg" title with a 6kg SKU/price selected. Gas
    // detail pages always show exactly the one product that was navigated to.
    const twelve = makeProduct({
      id: 'g1',
      sku: 'ELF-12KG-DO',
      size_kg: '12.00',
      variant_label: '12 kg (đỏ)',
    })
    const six = makeProduct({
      ...twelve,
      id: 'g2',
      sku: 'ELF-6KG-DO',
      size_kg: '6.00',
      price: '350000.00',
      variant_label: '6 kg (đỏ)',
    })

    render(<ProductDetail product={twelve} variants={[twelve, six]} />)

    expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument()
    expect(screen.queryByRole('radio', { name: /6 kg/ })).not.toBeInTheDocument()
  })
})

describe('ProductDetail gas title/SKU consistency', () => {
  it("always shows the navigated-to gas product's own title, SKU and price", () => {
    // Regression guard for #342: previously, selecting a sibling in the (now
    // removed) gas selector changed the SKU/price shown while the <h1> title
    // stayed fixed to the originally loaded product. With no selector, the
    // title/SKU/price can never drift apart.
    const thuduc12 = makeProduct({
      id: 'g1',
      sku: 'THUDUC-12KG',
      name: 'Bình gas Thủ Đức 12kg',
      size_kg: '12.00',
      price: '625000.00',
      variant_label: '12 kg',
    })
    const thuduc6 = makeProduct({
      ...thuduc12,
      id: 'g2',
      sku: 'THUDUC-6KG-NHUA',
      name: 'Bình gas Thủ Đức 6kg (vỏ nhựa)',
      size_kg: '6.00',
      price: '320000.00',
      variant_label: '6 kg (vỏ nhựa)',
    })

    render(<ProductDetail product={thuduc12} variants={[thuduc12, thuduc6]} />)

    expect(screen.getByRole('heading', { name: 'Bình gas Thủ Đức 12kg' })).toBeInTheDocument()
    expect(screen.getByText('SKU THUDUC-12KG')).toBeInTheDocument()
    expect(screen.queryByText('SKU THUDUC-6KG-NHUA')).not.toBeInTheDocument()
    expect(screen.queryByText(/320\.000/)).not.toBeInTheDocument()
  })
})
