import { apiClient } from '@/lib/api/client'

export type CouponDiscountType = 'percent' | 'fixed'

export interface CouponValidateResponse {
  code: string
  discount_type: CouponDiscountType
  value: string
  discount_amount: string
  min_order: string
}

export interface Coupon {
  id: string
  code: string
  discount_type: CouponDiscountType
  value: string
  min_order: string
  max_discount: string | null
  usage_limit: number | null
  used_count: number
  per_user_limit: number | null
  active: boolean
  starts_at: string | null
  ends_at: string | null
  created_at: string
  updated_at: string
}

export interface CouponListResponse {
  items: Coupon[]
  total: number
  page: number
  limit: number
  has_more: boolean
}

export interface CouponInput {
  code?: string
  discount_type?: CouponDiscountType
  value?: string
  min_order?: string
  max_discount?: string | null
  usage_limit?: number | null
  per_user_limit?: number | null
  active?: boolean
  starts_at?: string | null
  ends_at?: string | null
}

export async function validateCoupon(
  code: string,
  subtotal: number
): Promise<CouponValidateResponse> {
  const response = await apiClient.post<CouponValidateResponse>('/api/v1/coupons/validate', {
    code,
    subtotal,
  })
  return response.data
}

export async function listCoupons(params?: {
  active?: boolean
  search?: string
}): Promise<CouponListResponse> {
  const response = await apiClient.get<CouponListResponse>('/api/v1/admin/coupons', { params })
  return response.data
}

export async function createCoupon(data: CouponInput): Promise<Coupon> {
  const response = await apiClient.post<Coupon>('/api/v1/admin/coupons', data)
  return response.data
}

export async function updateCoupon(id: string, data: CouponInput): Promise<Coupon> {
  const response = await apiClient.patch<Coupon>(`/api/v1/admin/coupons/${id}`, data)
  return response.data
}
