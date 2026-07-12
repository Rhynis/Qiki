import { apiClient } from '@/lib/api/client'

export interface PriceSubscriptionAck {
  message: string
}

export async function subscribePriceAlerts(
  email: string,
  consent: boolean
): Promise<PriceSubscriptionAck> {
  const response = await apiClient.post<PriceSubscriptionAck>('/api/v1/price-alerts/subscribe', {
    email,
    consent,
  })
  return response.data
}

export async function confirmPriceAlerts(token: string): Promise<PriceSubscriptionAck> {
  const response = await apiClient.post<PriceSubscriptionAck>('/api/v1/price-alerts/confirm', {
    token,
  })
  return response.data
}

export async function unsubscribePriceAlerts(token: string): Promise<PriceSubscriptionAck> {
  const response = await apiClient.post<PriceSubscriptionAck>('/api/v1/price-alerts/unsubscribe', {
    token,
  })
  return response.data
}
