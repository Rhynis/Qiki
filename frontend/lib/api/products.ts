import { apiClient } from '@/lib/api/client'
import type {
  Product,
  ProductCategory,
  ProductCreateInput,
  ProductListResponse,
  ProductSearchParams,
  ProductUpdateInput,
} from '@/types/product'

export async function getProducts(params: ProductSearchParams = {}): Promise<ProductListResponse> {
  const response = await apiClient.get<ProductListResponse>('/api/v1/products', { params })
  return response.data
}

export async function getProduct(productId: string): Promise<Product> {
  const response = await apiClient.get<Product>(`/api/v1/products/${productId}`)
  return response.data
}

export async function getProductBySku(sku: string): Promise<Product> {
  const response = await apiClient.get<Product>(`/api/v1/products/sku/${sku}`)
  return response.data
}

export async function getProductBrands(category?: ProductCategory): Promise<string[]> {
  const response = await apiClient.get<string[]>('/api/v1/products/brands', {
    params: category ? { category } : undefined,
  })
  return response.data
}

export async function createProduct(data: ProductCreateInput): Promise<Product> {
  const response = await apiClient.post<Product>('/api/v1/products', data)
  return response.data
}

export async function updateProduct(productId: string, data: ProductUpdateInput): Promise<Product> {
  const response = await apiClient.patch<Product>(`/api/v1/products/${productId}`, data)
  return response.data
}

export async function deleteProduct(productId: string): Promise<void> {
  await apiClient.delete(`/api/v1/products/${productId}`)
}

export async function getLowStockProducts(threshold = 10): Promise<Product[]> {
  const response = await apiClient.get<Product[]>('/api/v1/admin/products/low-stock', {
    params: { threshold },
  })
  return response.data
}
