'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo } from 'react'
import { toast } from 'sonner'
import * as wishlistApi from '@/lib/api/wishlist'
import { useAuth } from '@/lib/hooks/use-auth'

export const wishlistKeys = {
  all: ['wishlist'] as const,
}

/** The current customer's saved products (only fetched when authenticated). */
export function useWishlist() {
  const { isAuthenticated } = useAuth()
  const query = useQuery({
    queryKey: wishlistKeys.all,
    queryFn: wishlistApi.getWishlist,
    enabled: isAuthenticated,
  })
  const products = useMemo(() => query.data ?? [], [query.data])
  const savedIds = useMemo(() => new Set(products.map((product) => product.id)), [products])

  return { ...query, products, savedIds, isAuthenticated }
}

/** Toggle a product in the wishlist; pass the current saved state. */
export function useToggleWishlist() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ productId, saved }: { productId: string; saved: boolean }) =>
      saved ? wishlistApi.removeFromWishlist(productId) : wishlistApi.addToWishlist(productId),
    onSuccess: async (_data, variables) => {
      await queryClient.invalidateQueries({ queryKey: wishlistKeys.all })
      toast.success(variables.saved ? 'Đã bỏ khỏi yêu thích' : 'Đã lưu vào yêu thích')
    },
    onError: () => {
      toast.error('Không thể cập nhật danh sách yêu thích. Vui lòng thử lại.')
    },
  })
}
