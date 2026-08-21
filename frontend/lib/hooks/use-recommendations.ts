'use client'

import { useQuery } from '@tanstack/react-query'
import { getProductRecommendations } from '@/lib/api/products'

/** Ranked "you might also like" suggestions for one product. */
export function useRecommendedProducts(productId: string, limit = 6) {
  return useQuery({
    queryKey: ['product-recommendations', productId, limit],
    queryFn: () => getProductRecommendations(productId, limit),
    enabled: Boolean(productId),
    // Non-critical widget: fail fast and render nothing instead of retry-storming
    // (a slow/unavailable recommendations endpoint must never block the product page).
    retry: false,
    staleTime: 60_000,
  })
}
