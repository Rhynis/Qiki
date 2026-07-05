import { apiClient } from '@/lib/api/client'

export type UserRole = 'customer' | 'staff' | 'admin'

export interface User {
  id: string
  email: string | null
  email_verified: boolean
  full_name: string | null
  phone: string | null
  address: string | null
  delivery_ward: string | null
  delivery_city: string | null
  delivery_notes: string | null
  role: UserRole
  is_active: boolean
  created_at: string
}

export interface ProfileUpdate {
  full_name?: string
  phone?: string
  address?: string
  delivery_ward?: string
  delivery_city?: string
  delivery_notes?: string
}

export interface RegisterData {
  email?: string
  password: string
  full_name: string
  phone: string
}

export interface LoginResponse {
  token_type: 'bearer'
  user: User
}

export type TokenResponse = LoginResponse

export async function register(data: RegisterData): Promise<User> {
  const response = await apiClient.post<User>('/api/v1/auth/register', data)
  return response.data
}

export async function login(identifier: string, password: string): Promise<LoginResponse> {
  const response = await apiClient.post<LoginResponse>('/api/v1/auth/login', {
    identifier,
    password,
  })
  return response.data
}

export async function logout(): Promise<void> {
  await apiClient.post('/api/v1/auth/logout')
}

export async function refreshToken(): Promise<TokenResponse> {
  const response = await apiClient.post<TokenResponse>('/api/v1/auth/refresh')
  return response.data
}

export async function getCurrentUser(): Promise<User> {
  const response = await apiClient.get<User>('/api/v1/auth/me')
  return response.data
}

export async function updateProfile(data: ProfileUpdate): Promise<User> {
  const response = await apiClient.patch<User>('/api/v1/auth/me', data)
  return response.data
}

export async function changePassword(oldPassword: string, newPassword: string): Promise<void> {
  await apiClient.post('/api/v1/auth/password/change', {
    old_password: oldPassword,
    new_password: newPassword,
  })
}

export async function requestPasswordReset(email: string): Promise<void> {
  await apiClient.post('/api/v1/auth/password/reset-request', { email })
}

export async function resetPassword(token: string, newPassword: string): Promise<void> {
  await apiClient.post('/api/v1/auth/password/reset', {
    token,
    new_password: newPassword,
  })
}

export async function requestEmailOtp(email: string): Promise<void> {
  await apiClient.post('/api/v1/auth/email/otp-request', { email })
}

export async function verifyEmailOtp(email: string, code: string): Promise<void> {
  await apiClient.post('/api/v1/auth/email/otp-verify', { email, code })
}
