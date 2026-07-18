import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithIntl } from '@/tests/i18n-render'
import { PriceAlertSubscribeForm } from '@/components/price-alerts/subscribe-form'
import { TokenActionClient } from '@/components/price-alerts/token-action-client'

const apiMocks = vi.hoisted(() => ({
  subscribePriceAlerts: vi.fn(),
  confirmPriceAlerts: vi.fn(),
  unsubscribePriceAlerts: vi.fn(),
}))

const searchParams = vi.hoisted(() => ({ value: new URLSearchParams() }))

vi.mock('next/navigation', () => ({
  useSearchParams: () => searchParams.value,
}))

vi.mock('@/lib/api/price-alerts', () => ({
  subscribePriceAlerts: apiMocks.subscribePriceAlerts,
  confirmPriceAlerts: apiMocks.confirmPriceAlerts,
  unsubscribePriceAlerts: apiMocks.unsubscribePriceAlerts,
}))

describe('PriceAlertSubscribeForm', () => {
  beforeEach(() => {
    apiMocks.subscribePriceAlerts.mockReset()
  })

  it('subscribes with the entered email and shows the returned message', async () => {
    const user = userEvent.setup()
    apiMocks.subscribePriceAlerts.mockResolvedValueOnce({ message: 'Đã gửi email xác nhận.' })
    renderWithIntl(<PriceAlertSubscribeForm />)

    await user.type(screen.getByLabelText('Email nhận thông báo giá'), 'buyer@example.com')
    await user.click(screen.getByRole('button', { name: 'Đăng ký nhận giá' }))

    await waitFor(() => {
      expect(apiMocks.subscribePriceAlerts).toHaveBeenCalledWith('buyer@example.com', true)
    })
    expect(await screen.findByText('Đã gửi email xác nhận.')).toBeInTheDocument()
  })

  it('blocks submit without consent', async () => {
    const user = userEvent.setup()
    renderWithIntl(<PriceAlertSubscribeForm />)

    await user.type(screen.getByLabelText('Email nhận thông báo giá'), 'buyer@example.com')
    await user.click(screen.getByLabelText(/Tôi đồng ý nhận email/)) // uncheck consent
    await user.click(screen.getByRole('button', { name: 'Đăng ký nhận giá' }))

    expect(await screen.findByText('Vui lòng đồng ý nhận email thông báo giá')).toBeInTheDocument()
    expect(apiMocks.subscribePriceAlerts).not.toHaveBeenCalled()
  })
})

describe('TokenActionClient', () => {
  beforeEach(() => {
    apiMocks.confirmPriceAlerts.mockReset()
  })

  it('shows an invalid message when the token is missing', () => {
    searchParams.value = new URLSearchParams()
    renderWithIntl(<TokenActionClient variant="confirm" />)

    expect(screen.getByText('Liên kết xác nhận không hợp lệ hoặc đã hết hạn.')).toBeInTheDocument()
  })

  it('runs the action with the token only when the button is clicked', async () => {
    const user = userEvent.setup()
    searchParams.value = new URLSearchParams('token=abc123')
    apiMocks.confirmPriceAlerts.mockResolvedValueOnce({ message: 'Đã xác nhận.' })
    renderWithIntl(<TokenActionClient variant="confirm" />)

    // Not run on mount (avoids email-scanner auto-triggering).
    expect(apiMocks.confirmPriceAlerts).not.toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Xác nhận đăng ký' }))

    await waitFor(() => expect(apiMocks.confirmPriceAlerts).toHaveBeenCalledWith('abc123'))
    expect(await screen.findByText('Đã xác nhận.')).toBeInTheDocument()
  })
})
