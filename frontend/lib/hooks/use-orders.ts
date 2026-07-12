'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import * as ordersApi from '@/lib/api/orders'
import type {
  CheckoutRequest,
  GuestOrderLookup,
  OrderCancelRequest,
  OrderSearchParams,
  OrderStatusUpdate,
} from '@/types/order'

export const orderKeys = {
  all: ['orders'] as const,
  lists: () => [...orderKeys.all, 'list'] as const,
  myList: (params: OrderSearchParams) => [...orderKeys.lists(), 'me', params] as const,
  adminList: (params: OrderSearchParams) => [...orderKeys.lists(), 'admin', params] as const,
  details: () => [...orderKeys.all, 'detail'] as const,
  detail: (orderId: string, phone?: string) => [...orderKeys.details(), orderId, phone] as const,
  statistics: () => [...orderKeys.all, 'statistics'] as const,
}

export function useCreateOrder() {
  return useMutation({
    mutationFn: ({ data, idempotencyKey }: { data: CheckoutRequest; idempotencyKey: string }) =>
      ordersApi.createOrder(data, idempotencyKey),
  })
}

export function useLookupOrder() {
  return useMutation({
    mutationFn: (data: GuestOrderLookup) => ordersApi.lookupOrder(data),
  })
}

export function useMyOrders(params: OrderSearchParams = {}) {
  return useQuery({
    queryKey: orderKeys.myList(params),
    queryFn: () => ordersApi.getMyOrders(params),
  })
}

export function useOrder(orderId: string, phone?: string) {
  return useQuery({
    queryKey: orderKeys.detail(orderId, phone),
    queryFn: () => ordersApi.getOrder(orderId, phone),
    enabled: Boolean(orderId),
  })
}

export function useCancelOrder() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ orderId, data }: { orderId: string; data: OrderCancelRequest }) =>
      ordersApi.cancelOrder(orderId, data),
    onSuccess: async (order) => {
      await queryClient.invalidateQueries({ queryKey: orderKeys.all })
      queryClient.setQueryData(orderKeys.detail(order.id), order)
      toast.success('Đã hủy đơn hàng')
    },
  })
}

export function useAdminOrders(params: OrderSearchParams = {}) {
  return useQuery({
    queryKey: orderKeys.adminList(params),
    queryFn: () => ordersApi.getAdminOrders(params),
  })
}

export function useUpdateOrderStatus() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ orderId, data }: { orderId: string; data: OrderStatusUpdate }) =>
      ordersApi.updateOrderStatus(orderId, data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: orderKeys.all })
      toast.success('Đã cập nhật trạng thái')
    },
  })
}

export function useOrderStatistics() {
  return useQuery({
    queryKey: orderKeys.statistics(),
    queryFn: ordersApi.getOrderStatistics,
  })
}

export function useIssueInvoice() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (orderId: string) => ordersApi.issueInvoice(orderId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: orderKeys.all })
      toast.success('Đã xuất hóa đơn')
    },
    onError: () => {
      toast.error('Không thể xuất hóa đơn')
    },
  })
}
