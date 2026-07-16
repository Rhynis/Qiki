import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { WishlistButton } from '@/components/shop/wishlist-button'
import { renderWithIntl as render } from '../i18n-render'

const { routerMocks, toggleMock, wishlistState, toastMocks } = vi.hoisted(() => ({
  routerMocks: { push: vi.fn() },
  toggleMock: { mutate: vi.fn(), isPending: false },
  wishlistState: { savedIds: new Set<string>(), isAuthenticated: false },
  toastMocks: { info: vi.fn(), success: vi.fn(), error: vi.fn() },
}))

vi.mock('next/navigation', () => ({
  useRouter: () => routerMocks,
  usePathname: () => '/products/p1',
}))

vi.mock('@/lib/hooks/use-wishlist', () => ({
  useWishlist: () => wishlistState,
  useToggleWishlist: () => toggleMock,
}))

vi.mock('sonner', () => ({ toast: toastMocks }))

describe('WishlistButton', () => {
  beforeEach(() => {
    routerMocks.push.mockReset()
    toggleMock.mutate.mockReset()
    toastMocks.info.mockReset()
    wishlistState.savedIds = new Set()
    wishlistState.isAuthenticated = false
  })

  it('shows a toast to a guest without redirecting or toggling', async () => {
    const user = userEvent.setup()
    render(<WishlistButton productId="p1" />)

    await user.click(screen.getByRole('button', { name: 'Lưu vào yêu thích' }))

    expect(toastMocks.info).toHaveBeenCalled()
    // The guest stays on the page — no redirect to /login.
    expect(routerMocks.push).not.toHaveBeenCalled()
    expect(toggleMock.mutate).not.toHaveBeenCalled()
  })

  it('adds when authenticated and not yet saved', async () => {
    wishlistState.isAuthenticated = true
    const user = userEvent.setup()
    render(<WishlistButton productId="p1" />)

    await user.click(screen.getByRole('button', { name: 'Lưu vào yêu thích' }))

    expect(toggleMock.mutate).toHaveBeenCalledWith({ productId: 'p1', saved: false })
  })

  it('shows a pressed state and removes when already saved', async () => {
    wishlistState.isAuthenticated = true
    wishlistState.savedIds = new Set(['p1'])
    const user = userEvent.setup()
    render(<WishlistButton productId="p1" />)

    const button = screen.getByRole('button', { name: 'Bỏ khỏi yêu thích' })
    expect(button).toHaveAttribute('aria-pressed', 'true')

    await user.click(button)

    expect(toggleMock.mutate).toHaveBeenCalledWith({ productId: 'p1', saved: true })
  })
})
