import axios, { type AxiosError, type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'
import { v4 as uuidv4 } from 'uuid'

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    public detail: string
  ) {
    super(detail)
    this.name = 'ApiError'
  }
}

/** Create an Axios instance configured for the GasBot API. */
function createApiClient(): AxiosInstance {
  const client = axios.create({
    baseURL: '',
    timeout: 30000,
    withCredentials: true,
    headers: { 'Content-Type': 'application/json' },
  })

  client.interceptors.request.use((config: InternalAxiosRequestConfig) => {
    const method = config.method?.toUpperCase()
    if (method === 'POST' || method === 'PATCH' || method === 'PUT') {
      if (!config.headers['Idempotency-Key']) {
        config.headers['Idempotency-Key'] = uuidv4()
      }
    }

    return config
  })

  client.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
      const originalRequest = error.config as
        | (InternalAxiosRequestConfig & { _retry?: boolean })
        | undefined
      const requestUrl = originalRequest?.url ?? ''

      if (
        error.response?.status === 401 &&
        originalRequest &&
        !originalRequest._retry &&
        !requestUrl.includes('/auth/login') &&
        !requestUrl.includes('/auth/refresh') &&
        !requestUrl.includes('/auth/logout')
      ) {
        originalRequest._retry = true
        await client.post('/api/v1/auth/refresh')
        return client(originalRequest)
      }

      if (error.response) {
        const data = error.response.data as { detail?: string; error_code?: string }
        throw new ApiError(
          error.response.status,
          data.error_code ?? 'unknown_error',
          data.detail ?? error.message
        )
      }
      if (error.request) {
        throw new ApiError(0, 'network_error', 'Network error - please check your connection')
      }
      throw new ApiError(0, 'unknown_error', error.message)
    }
  )

  return client
}

export const apiClient = createApiClient()
