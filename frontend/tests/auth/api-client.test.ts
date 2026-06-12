import { describe, expect, it } from 'vitest'
import { apiClient } from '@/lib/api/client'

describe('api client auth transport', () => {
  it('uses credentials for httpOnly auth cookies', () => {
    expect(apiClient.defaults.baseURL).toBe('')
    expect(apiClient.defaults.withCredentials).toBe(true)
    expect(apiClient.defaults.headers.common.Authorization).toBeUndefined()
  })
})
