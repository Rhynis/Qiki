import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LoginForm } from '@/components/auth/login-form'
import { PasswordResetRequestForm } from '@/components/auth/password-reset-form'
import { RegisterForm } from '@/components/auth/register-form'

const authMocks = vi.hoisted(() => ({
  login: vi.fn(),
  register: vi.fn(),
}))

const authApiMocks = vi.hoisted(() => ({
  requestPasswordReset: vi.fn(),
}))

vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(),
}))

vi.mock('@/lib/hooks/use-auth', () => ({
  useAuth: () => ({
    login: authMocks.login,
    register: authMocks.register,
    isLoading: false,
  }),
}))

vi.mock('@/lib/api/auth', () => ({
  requestPasswordReset: authApiMocks.requestPasswordReset,
}))

describe('auth forms', () => {
  beforeEach(() => {
    authMocks.login.mockReset()
    authMocks.register.mockReset()
    authApiMocks.requestPasswordReset.mockReset()
  })

  it('shows the required login identifier inline and clears it when filled', async () => {
    const user = userEvent.setup()
    render(<LoginForm />)

    const identifier = screen.getByLabelText('Số điện thoại hoặc email')
    await user.type(identifier, '0')
    await user.clear(identifier)

    expect(await screen.findByText('Vui lòng nhập số điện thoại hoặc email')).toBeInTheDocument()

    await user.type(identifier, '0903026306')

    await waitFor(() => {
      expect(screen.queryByText('Vui lòng nhập số điện thoại hoặc email')).not.toBeInTheDocument()
    })
  })

  it('logs in by phone and shows submit errors inline', async () => {
    const user = userEvent.setup()
    authMocks.login.mockRejectedValueOnce(
      new Error('Số điện thoại/email hoặc mật khẩu không đúng.')
    )
    render(<LoginForm />)

    await user.type(screen.getByLabelText('Số điện thoại hoặc email'), '0903026306')
    await user.type(screen.getByLabelText('Mật khẩu'), 'Abc123')
    await user.click(screen.getByRole('button', { name: 'Đăng nhập' }))

    expect(authMocks.login).toHaveBeenCalledWith('0903026306', 'Abc123', '/')
    expect(
      await screen.findByText('Số điện thoại/email hoặc mật khẩu không đúng.')
    ).toBeInTheDocument()
  })

  it('formats register phone input and submits digits only', async () => {
    const user = userEvent.setup()
    authMocks.register.mockResolvedValueOnce(undefined)
    render(<RegisterForm />)

    await user.type(screen.getByLabelText('Họ và tên'), 'Nguyen Van A')
    await user.type(screen.getByLabelText('Email (không bắt buộc)'), 'ten@gmail.com')
    await user.type(screen.getByLabelText('Số điện thoại'), '0903026306')
    await user.type(screen.getByLabelText('Mật khẩu'), 'Abc123')
    await user.type(screen.getByLabelText('Xác nhận mật khẩu'), 'Abc123')

    expect(screen.getByLabelText('Số điện thoại')).toHaveValue('090 3026 306')

    await user.click(screen.getByRole('button', { name: 'Đăng ký' }))

    await waitFor(() => {
      expect(authMocks.register).toHaveBeenCalledWith(
        expect.objectContaining({ phone: '0903026306' })
      )
    })
  })

  it('surfaces the duplicate-email error inline on register', async () => {
    const user = userEvent.setup()
    authMocks.register.mockRejectedValueOnce(new Error('Email này đã được sử dụng.'))
    render(<RegisterForm />)

    await user.type(screen.getByLabelText('Họ và tên'), 'Nguyen Van A')
    await user.type(screen.getByLabelText('Email (không bắt buộc)'), 'ten@gmail.com')
    await user.type(screen.getByLabelText('Số điện thoại'), '0903026306')
    await user.type(screen.getByLabelText('Mật khẩu'), 'Abc123')
    await user.type(screen.getByLabelText('Xác nhận mật khẩu'), 'Abc123')
    await user.click(screen.getByRole('button', { name: 'Đăng ký' }))

    expect(await screen.findByText('Email này đã được sử dụng.')).toBeInTheDocument()
  })

  it('shows invalid register phone inline and clears it when corrected', async () => {
    const user = userEvent.setup()
    render(<RegisterForm />)

    const phone = screen.getByLabelText('Số điện thoại')
    await user.type(phone, '123')
    await user.tab()

    expect(screen.getByText('Số điện thoại không hợp lệ, ví dụ: 090 3026 306')).toBeInTheDocument()

    await user.clear(phone)
    await user.type(phone, '0903026306')

    await waitFor(() => {
      expect(
        screen.queryByText('Số điện thoại không hợp lệ, ví dụ: 090 3026 306')
      ).not.toBeInTheDocument()
    })
  })

  it('shows forgot-password success inline', async () => {
    const user = userEvent.setup()
    authApiMocks.requestPasswordReset.mockResolvedValueOnce(undefined)
    render(<PasswordResetRequestForm />)

    await user.type(screen.getByLabelText('Email'), 'ten@gmail.com')
    await user.click(screen.getByRole('button', { name: 'Gửi hướng dẫn' }))

    expect(
      await screen.findByText('Nếu email tồn tại, hướng dẫn đặt lại mật khẩu đã được gửi.')
    ).toBeInTheDocument()
  })
})
