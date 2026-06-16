import { beforeEach, describe, expect, it } from 'vitest'
import { useAuthStore } from '@/lib/stores/auth-store'
import type { User } from '@/lib/api/auth'

const user: User = {
  id: 'user-id',
  email: 'admin@example.com',
  email_verified: true,
  full_name: 'Admin User',
  phone: '+84901234567',
  role: 'admin',
  is_active: true,
  created_at: '2026-05-26T00:00:00Z',
}

describe('auth store', () => {
  beforeEach(() => {
    useAuthStore.getState().clearAuth()
    localStorage.clear()
  })

  it('stores user and session metadata without tokens', () => {
    useAuthStore.getState().setUser(user)
    useAuthStore.getState().setSession({ tokenType: 'bearer' })

    expect(useAuthStore.getState().user?.role).toBe('admin')
    expect(localStorage.getItem('gasbot-auth')).not.toContain('access_token')
    expect(localStorage.getItem('gasbot-auth')).not.toContain('refresh_token')
  })

  it('clears auth state', () => {
    useAuthStore.getState().setUser(user)
    useAuthStore.getState().setSession({ tokenType: 'bearer' })

    useAuthStore.getState().clearAuth()

    expect(useAuthStore.getState().user).toBeNull()
    expect(useAuthStore.getState().session).toBeNull()
  })
})
