'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as couponsApi from '@/lib/api/coupons'
import type { CouponInput } from '@/lib/api/coupons'

export const couponKeys = {
  all: ['coupons'] as const,
  list: (params?: { active?: boolean; search?: string }) =>
    [...couponKeys.all, 'list', params ?? {}] as const,
}

export function useCoupons(params?: { active?: boolean; search?: string }) {
  return useQuery({
    queryKey: couponKeys.list(params),
    queryFn: () => couponsApi.listCoupons(params),
  })
}

export function useCreateCoupon() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CouponInput) => couponsApi.createCoupon(data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: couponKeys.all }),
  })
}

export function useUpdateCoupon() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: CouponInput }) =>
      couponsApi.updateCoupon(id, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: couponKeys.all }),
  })
}
