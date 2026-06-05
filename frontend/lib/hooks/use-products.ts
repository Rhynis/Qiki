'use client'

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import * as productsApi from '@/lib/api/products'
import type {
  ProductCategory,
  ProductCreateInput,
  ProductSearchParams,
  ProductUpdateInput,
} from '@/types/product'

export const productKeys = {
  all: ['products'] as const,
  lists: () => [...productKeys.all, 'list'] as const,
  list: (params: ProductSearchParams) => [...productKeys.lists(), params] as const,
  brands: (category?: ProductCategory) =>
    [...productKeys.all, 'brands', category ?? 'all'] as const,
  details: () => [...productKeys.all, 'detail'] as const,
  detail: (productId: string) => [...productKeys.details(), productId] as const,
  lowStock: (threshold: number) => [...productKeys.all, 'low-stock', threshold] as const,
}

export function useProducts(params: ProductSearchParams = {}) {
  return useQuery({
    queryKey: productKeys.list(params),
    queryFn: () => productsApi.getProducts(params),
  })
}

export function useInfiniteProducts(params: ProductSearchParams = {}) {
  const limit = params.limit ?? 20
  return useInfiniteQuery({
    queryKey: [...productKeys.lists(), 'infinite', params],
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      productsApi.getProducts({
        ...params,
        skip: pageParam * limit,
        limit,
      }),
    getNextPageParam: (lastPage) => (lastPage.has_more ? lastPage.page : undefined),
  })
}

export function useProduct(productId: string) {
  return useQuery({
    queryKey: productKeys.detail(productId),
    queryFn: () => productsApi.getProduct(productId),
    enabled: Boolean(productId),
  })
}

export function useProductBrands(category?: ProductCategory) {
  return useQuery({
    queryKey: productKeys.brands(category),
    queryFn: () => productsApi.getProductBrands(category),
  })
}

export function useLowStockProducts(threshold = 10) {
  return useQuery({
    queryKey: productKeys.lowStock(threshold),
    queryFn: () => productsApi.getLowStockProducts(threshold),
  })
}

export function useCreateProduct() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: ProductCreateInput) => productsApi.createProduct(data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: productKeys.all })
      toast.success('Đã tạo sản phẩm')
    },
  })
}

export function useUpdateProduct() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ productId, data }: { productId: string; data: ProductUpdateInput }) =>
      productsApi.updateProduct(productId, data),
    onSuccess: async (product) => {
      await queryClient.invalidateQueries({ queryKey: productKeys.all })
      queryClient.setQueryData(productKeys.detail(product.id), product)
      toast.success('Đã cập nhật sản phẩm')
    },
  })
}

export function useDeleteProduct() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (productId: string) => productsApi.deleteProduct(productId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: productKeys.all })
      toast.success('Đã ẩn sản phẩm')
    },
  })
}
