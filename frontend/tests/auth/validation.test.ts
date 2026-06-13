import { describe, expect, it } from 'vitest'
import { loginSchema, passwordResetSchema, registerSchema } from '@/lib/validations/auth'

describe('auth validation schemas', () => {
  it('accepts valid registration data', () => {
    const result = registerSchema.safeParse({
      full_name: 'Nguyen Van A',
      email: 'user@example.com',
      phone: '090 1234 567',
      password: 'Abc123',
      confirmPassword: 'Abc123',
    })

    expect(result.success).toBe(true)
    expect(result.success ? result.data.phone : '').toBe('0901234567')
  })

  it('rejects passwords shorter than six characters with Vietnamese messages', () => {
    const result = registerSchema.safeParse({
      full_name: 'Nguyen Van A',
      email: 'user@example.com',
      phone: '0901234567',
      password: 'Abc12',
      confirmPassword: 'Abc12',
    })

    expect(result.success).toBe(false)
    expect(result.success ? '' : result.error.issues[0]?.message).toBe('Mật khẩu tối thiểu 6 ký tự')
  })

  it('rejects passwords without uppercase or digits', () => {
    const missingUppercase = registerSchema.safeParse({
      full_name: 'Nguyen Van A',
      email: 'user@example.com',
      phone: '0901234567',
      password: 'abc123',
      confirmPassword: 'abc123',
    })
    const missingDigit = passwordResetSchema.safeParse({
      token: 'reset-token',
      newPassword: 'Abcdef',
      confirmNewPassword: 'Abcdef',
    })

    expect(missingUppercase.success ? '' : missingUppercase.error.issues[0]?.message).toBe(
      'Mật khẩu cần có ít nhất 1 chữ hoa'
    )
    expect(missingDigit.success ? '' : missingDigit.error.issues[0]?.message).toBe(
      'Mật khẩu cần có ít nhất 1 chữ số'
    )
  })

  it('rejects mismatched confirmation password', () => {
    const result = registerSchema.safeParse({
      full_name: 'Nguyen Van A',
      email: 'user@example.com',
      phone: '0901234567',
      password: 'Abc123',
      confirmPassword: 'Khac123',
    })

    expect(result.success).toBe(false)
    expect(result.success ? '' : result.error.issues.at(-1)?.message).toBe(
      'Mật khẩu xác nhận không khớp'
    )
  })

  it('requires login email and password', () => {
    const result = loginSchema.safeParse({ email: '', password: '' })

    expect(result.success).toBe(false)
  })
})
