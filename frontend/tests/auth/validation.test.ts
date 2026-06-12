import { describe, expect, it } from 'vitest'
import { loginSchema, registerSchema } from '@/lib/validations/auth'

describe('auth validation schemas', () => {
  it('accepts valid registration data', () => {
    const result = registerSchema.safeParse({
      full_name: 'Nguyen Van A',
      email: 'user@example.com',
      phone: '0901234567',
      password: 'matkhau1',
      confirmPassword: 'matkhau1',
    })

    expect(result.success).toBe(true)
  })

  it('rejects passwords shorter than eight characters with Vietnamese messages', () => {
    const result = registerSchema.safeParse({
      full_name: 'Nguyen Van A',
      email: 'user@example.com',
      phone: '0901234567',
      password: '1234567',
      confirmPassword: '1234567',
    })

    expect(result.success).toBe(false)
    expect(result.success ? '' : result.error.issues[0]?.message).toBe('Mật khẩu tối thiểu 8 ký tự')
  })

  it('rejects mismatched confirmation password', () => {
    const result = registerSchema.safeParse({
      full_name: 'Nguyen Van A',
      email: 'user@example.com',
      phone: '0901234567',
      password: 'matkhau1',
      confirmPassword: 'khacmat1',
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
