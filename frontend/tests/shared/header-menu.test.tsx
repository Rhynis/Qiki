import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Header } from '@/components/shared/header'
import { UserMenu } from '@/components/shared/user-menu'
import type { User } from '@/lib/api/auth'

const routerMocks = vi.hoisted(() => ({
  push: vi.fn(),
}))

const authMocks = vi.hoisted(() => ({
  logout: vi.fn(),
  refreshUser: vi.fn(),
  user: {
    id: 'user-1',
    email: 'customer@example.com',
    email_verified: true,
    full_name: 'Khách Hàng Test',
    phone: '0903026306',
    role: 'customer',
    is_active: true,
    created_at: '2026-06-15T00:00:00.000Z',
  } satisfies User,
  isAuthenticated: true,
  isAdmin: false,
}))

vi.mock('next/navigation', () => ({
  useRouter: () => routerMocks,
}))

vi.mock('@/lib/hooks/use-auth', () => ({
  useAuth: () => ({
    user: authMocks.user,
    isAuthenticated: authMocks.isAuthenticated,
    isAdmin: authMocks.isAdmin,
    logout: authMocks.logout,
    refreshUser: authMocks.refreshUser,
  }),
}))

describe('header product navigation', () => {
  beforeEach(() => {
    routerMocks.push.mockReset()
    authMocks.logout.mockReset()
    authMocks.refreshUser.mockReset()
    authMocks.user = {
      id: 'user-1',
      email: 'customer@example.com',
      email_verified: true,
      full_name: 'Khách Hàng Test',
      phone: '0903026306',
      role: 'customer',
      is_active: true,
      created_at: '2026-06-15T00:00:00.000Z',
    }
    authMocks.isAuthenticated = true
    authMocks.isAdmin = false
  })

  it('renders the Sản phẩm parent as a /products link and keeps the category dropdown', async () => {
    const user = userEvent.setup()
    render(<Header />)

    const productsLink = screen.getByRole('link', { name: 'Sản phẩm' })
    expect(productsLink).toHaveAttribute('href', '/products')

    await user.hover(productsLink)
    expect(await screen.findByRole('menuitem', { name: 'Gas' })).toBeVisible()

    await user.click(screen.getByRole('menuitem', { name: 'Nước Uống' }))
    expect(routerMocks.push).toHaveBeenCalledWith('/products?category=nuoc_uong')
  })
})

describe('user menu interactions', () => {
  beforeEach(() => {
    authMocks.logout.mockReset()
    authMocks.refreshUser.mockReset()
    authMocks.user = {
      id: 'user-1',
      email: 'customer@example.com',
      email_verified: true,
      full_name: 'Khách Hàng Test',
      phone: '0903026306',
      role: 'customer',
      is_active: true,
      created_at: '2026-06-15T00:00:00.000Z',
    }
    authMocks.isAuthenticated = true
    authMocks.isAdmin = false
  })

  it('opens on hover and closes after the cursor leaves', async () => {
    const user = userEvent.setup()
    render(<UserMenu />)

    const trigger = screen.getByRole('button', { name: /Khách Hàng Test/ })
    await user.hover(trigger)

    expect(await screen.findByRole('menuitem', { name: 'Tài khoản' })).toBeVisible()

    await user.unhover(trigger)
    await waitFor(() => {
      expect(screen.queryByRole('menuitem', { name: 'Tài khoản' })).not.toBeInTheDocument()
    })
  })

  it('opens on click for tap-style interaction', async () => {
    const user = userEvent.setup({ skipHover: true })
    render(<UserMenu />)

    await user.click(screen.getByRole('button', { name: /Khách Hàng Test/ }))

    expect(await screen.findByRole('menuitem', { name: 'Tài khoản' })).toBeVisible()
  })
})
