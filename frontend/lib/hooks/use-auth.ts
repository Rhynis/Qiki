'use client'

import { useRouter } from 'next/navigation'
import { useCallback } from 'react'
import { toast } from 'sonner'
import * as authApi from '@/lib/api/auth'
import { useAuthStore } from '@/lib/stores/auth-store'
import type { RegisterFormValues } from '@/lib/validations/auth'

export function useAuth() {
  const router = useRouter()
  const { user, session, isLoading, error, setUser, setSession, setLoading, setError, clearAuth } =
    useAuthStore()

  const refreshUser = useCallback(async () => {
    setLoading(true)
    try {
      const currentUser = await authApi.getCurrentUser()
      setUser(currentUser)
      setSession({ tokenType: 'bearer' })
      setError(null)
      return currentUser
    } catch {
      clearAuth()
      return null
    } finally {
      setLoading(false)
    }
  }, [clearAuth, setError, setLoading, setSession, setUser])

  const login = async (identifier: string, password: string, redirectTo = '/') => {
    setLoading(true)
    try {
      const result = await authApi.login(identifier, password)
      setUser(result.user)
      setSession({ tokenType: result.token_type })
      setError(null)
      toast.success('Đăng nhập thành công')
      router.push(redirectTo)
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Đăng nhập thất bại'
      setError(message)
      throw caught
    } finally {
      setLoading(false)
    }
  }

  const register = async (data: RegisterFormValues) => {
    setLoading(true)
    try {
      await authApi.register({
        email: data.email ? data.email : undefined,
        password: data.password,
        full_name: data.full_name,
        phone: data.phone,
      })
      toast.success('Đăng ký thành công. Vui lòng đăng nhập.')
      router.push('/login')
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : 'Đăng ký thất bại'
      setError(message)
      throw caught
    } finally {
      setLoading(false)
    }
  }

  const logout = async () => {
    setLoading(true)
    try {
      await authApi.logout()
    } finally {
      clearAuth()
      setLoading(false)
      router.push('/')
    }
  }

  const changePassword = async (oldPassword: string, newPassword: string) => {
    await authApi.changePassword(oldPassword, newPassword)
    clearAuth()
    toast.success('Mật khẩu đã được cập nhật. Vui lòng đăng nhập lại.')
    router.push('/login')
  }

  return {
    user,
    session,
    isLoading,
    error,
    isAuthenticated: Boolean(user && session),
    isAdmin: user?.role === 'admin',
    isStaff: user?.role === 'staff' || user?.role === 'admin',
    login,
    logout,
    register,
    changePassword,
    refreshUser,
  }
}
