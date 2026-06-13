import { z } from 'zod'
import { isVietnameseMobilePhone, normalizePhoneDigits } from '@/utils/phone-format'

export const emailInvalidMessage = 'Email không hợp lệ, ví dụ: ten@gmail.com'
export const passwordHelpText = 'Mật khẩu tối thiểu 6 ký tự, có 1 chữ hoa và 1 chữ số.'
export const phoneInvalidMessage = 'Số điện thoại không hợp lệ, ví dụ: 090 3026 306'

export const passwordSchema = z
  .string()
  .min(6, 'Mật khẩu tối thiểu 6 ký tự')
  .max(128, 'Mật khẩu tối đa 128 ký tự')
  .regex(/[A-Z]/, 'Mật khẩu cần có ít nhất 1 chữ hoa')
  .regex(/\d/, 'Mật khẩu cần có ít nhất 1 chữ số')

export const loginSchema = z.object({
  email: z.string().min(1, 'Email không được để trống').email(emailInvalidMessage),
  password: z.string().min(1, 'Mật khẩu không được để trống'),
})

const phoneSchema = z
  .string()
  .trim()
  .transform(normalizePhoneDigits)
  .refine(isVietnameseMobilePhone, phoneInvalidMessage)

export const registerSchema = z
  .object({
    full_name: z.string().min(2, 'Họ tên phải có ít nhất 2 ký tự').max(255, 'Họ tên quá dài'),
    email: z.string().email(emailInvalidMessage),
    phone: phoneSchema,
    password: passwordSchema,
    confirmPassword: z.string(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: 'Mật khẩu xác nhận không khớp',
    path: ['confirmPassword'],
  })

export const passwordChangeSchema = z
  .object({
    oldPassword: z.string().min(1, 'Vui lòng nhập mật khẩu cũ'),
    newPassword: passwordSchema,
    confirmNewPassword: z.string(),
  })
  .refine((data) => data.newPassword === data.confirmNewPassword, {
    message: 'Mật khẩu xác nhận không khớp',
    path: ['confirmNewPassword'],
  })

export const passwordResetRequestSchema = z.object({
  email: z.string().email(emailInvalidMessage),
})

export const passwordResetSchema = z
  .object({
    token: z.string().optional(),
    newPassword: passwordSchema,
    confirmNewPassword: z.string(),
  })
  .refine((data) => data.newPassword === data.confirmNewPassword, {
    message: 'Mật khẩu xác nhận không khớp',
    path: ['confirmNewPassword'],
  })

export type LoginFormValues = z.infer<typeof loginSchema>
export type RegisterFormValues = z.infer<typeof registerSchema>
export type PasswordChangeFormValues = z.infer<typeof passwordChangeSchema>
export type PasswordResetRequestValues = z.infer<typeof passwordResetRequestSchema>
export type PasswordResetValues = z.infer<typeof passwordResetSchema>
