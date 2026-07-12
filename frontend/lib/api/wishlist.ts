import { apiClient } from '@/lib/api/client'
import type { Product } from '@/types/product'

export async function getWishlist(): Promise<Product[]> {
  const response = await apiClient.get<Product[]>('/api/v1/wishlist')
  return response.data
}

export async function addToWishlist(productId: string): Promise<void> {
  await apiClient.post(`/api/v1/wishlist/${productId}`)
}

export async function removeFromWishlist(productId: string): Promise<void> {
  await apiClient.delete(`/api/v1/wishlist/${productId}`)
}
