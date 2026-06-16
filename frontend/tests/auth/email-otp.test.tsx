import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { EmailOtpVerification } from '@/components/auth/email-otp-verification'

const apiMocks = vi.hoisted(() => ({
  requestEmailOtp: vi.fn(),
  verifyEmailOtp: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('@/lib/api/auth', () => ({
  requestEmailOtp: apiMocks.requestEmailOtp,
  verifyEmailOtp: apiMocks.verifyEmailOtp,
}))

describe('EmailOtpVerification', () => {
  beforeEach(() => {
    apiMocks.requestEmailOtp.mockReset()
    apiMocks.verifyEmailOtp.mockReset()
  })

  it('requests a code then verifies the entered OTP', async () => {
    const user = userEvent.setup()
    apiMocks.requestEmailOtp.mockResolvedValue(undefined)
    apiMocks.verifyEmailOtp.mockResolvedValue(undefined)
    const onVerified = vi.fn()
    render(<EmailOtpVerification email="user@example.com" onVerified={onVerified} />)

    await user.click(screen.getByRole('button', { name: 'Gửi mã xác minh' }))
    expect(apiMocks.requestEmailOtp).toHaveBeenCalledWith('user@example.com')

    await user.type(screen.getByLabelText('Mã xác minh'), '123456')
    await user.click(screen.getByRole('button', { name: 'Xác minh' }))

    await waitFor(() => {
      expect(apiMocks.verifyEmailOtp).toHaveBeenCalledWith('user@example.com', '123456')
    })
    expect(onVerified).toHaveBeenCalled()
  })

  it('shows an inline error when the code is rejected', async () => {
    const user = userEvent.setup()
    apiMocks.requestEmailOtp.mockResolvedValue(undefined)
    apiMocks.verifyEmailOtp.mockRejectedValueOnce(
      new Error('Mã xác minh không đúng hoặc đã hết hạn')
    )
    render(<EmailOtpVerification email="user@example.com" />)

    await user.click(screen.getByRole('button', { name: 'Gửi mã xác minh' }))
    await user.type(screen.getByLabelText('Mã xác minh'), '000000')
    await user.click(screen.getByRole('button', { name: 'Xác minh' }))

    expect(await screen.findByText('Mã xác minh không đúng hoặc đã hết hạn')).toBeInTheDocument()
  })
})
