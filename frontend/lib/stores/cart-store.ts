'use client'

import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'
import type { Product } from '@/types/product'

export interface CartItem {
  productId: string
  name: string
  brand: string
  sizeKg: number
  unit: string
  price: number
  quantity: number
  imageUrl?: string | null
}

interface CartState {
  items: CartItem[]
  addItem: (product: Product, quantity?: number) => void
  removeItem: (productId: string) => void
  updateQuantity: (productId: string, quantity: number) => void
  clearCart: () => void
  getTotal: () => number
  getItemCount: () => number
}

export const useCartStore = create<CartState>()(
  persist(
    (set, get) => ({
      items: [],
      addItem: (product, quantity = 1) => {
        const items = get().items
        const existing = items.find((item) => item.productId === product.id)
        if (existing) {
          set({
            items: items.map((item) =>
              item.productId === product.id ? { ...item, quantity: item.quantity + quantity } : item
            ),
          })
          return
        }
        set({
          items: [
            ...items,
            {
              productId: product.id,
              name: product.name,
              brand: product.brand,
              sizeKg: Number(product.size_kg),
              unit: product.unit,
              price: Number(product.price),
              quantity,
              imageUrl: product.image_url,
            },
          ],
        })
      },
      removeItem: (productId) =>
        set({ items: get().items.filter((item) => item.productId !== productId) }),
      updateQuantity: (productId, quantity) => {
        if (quantity <= 0) {
          get().removeItem(productId)
          return
        }
        set({
          items: get().items.map((item) =>
            item.productId === productId ? { ...item, quantity } : item
          ),
        })
      },
      clearCart: () => set({ items: [] }),
      getTotal: () => get().items.reduce((sum, item) => sum + item.price * item.quantity, 0),
      getItemCount: () => get().items.reduce((sum, item) => sum + item.quantity, 0),
    }),
    {
      name: 'gasbot-cart',
      storage: createJSONStorage(() => localStorage),
    }
  )
)
