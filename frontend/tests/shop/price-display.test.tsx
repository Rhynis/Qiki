import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PriceDisplay } from '@/components/shop/price-display'

describe('PriceDisplay', () => {
  it('shows the sale price, struck-through original, and -X% badge when on sale', () => {
    const { container } = render(<PriceDisplay listPrice="710000" salePrice="600000" />)

    expect(screen.getByText('-15%')).toBeInTheDocument()
    const struck = container.querySelector('.line-through')
    expect(struck).not.toBeNull()
    // The effective price (600.000) and the struck original (710.000) both render.
    expect(container.textContent).toContain('600.000')
    expect(container.textContent).toContain('710.000')
  })

  it('renders a single price when not on sale', () => {
    const { container } = render(<PriceDisplay listPrice="710000" salePrice={null} />)

    expect(screen.queryByText(/%$/)).not.toBeInTheDocument()
    expect(container.querySelector('.line-through')).toBeNull()
    expect(container.textContent).toContain('710.000')
  })

  it('ignores an invalid sale price (>= list) and shows the single list price', () => {
    const { container } = render(<PriceDisplay listPrice="710000" salePrice="800000" />)
    expect(container.querySelector('.line-through')).toBeNull()
    expect(container.textContent).toContain('710.000')
  })
})
