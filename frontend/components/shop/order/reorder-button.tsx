'use client'

import { RotateCcw } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { useState } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { reorder } from '@/lib/api/orders'
import { useCartStore } from '@/lib/stores/cart-store'
import type { ReorderItem } from '@/types/order'
import type { Product, ProductCategory, ProductUnit } from '@/types/product'

function toProduct(item: ReorderItem): Product {
  return {
    id: item.product_id,
    sku: item.sku,
    name: item.name,
    brand: item.brand,
    size_kg: item.size_kg,
    category: item.category as ProductCategory,
    unit: item.unit as ProductUnit,
    price: item.price,
    stock_quantity: item.stock_quantity,
    description: null,
    image_url: item.image_url,
    safety_info: null,
    pricing_note: null,
    parent_id: null,
    colour: null,
    variant_label: null,
    is_active: true,
    created_at: '',
    updated_at: '',
  }
}

export function ReorderButton({ orderId }: { orderId: string }) {
  const router = useRouter()
  const addItem = useCartStore((state) => state.addItem)
  const [isLoading, setIsLoading] = useState(false)

  const handleReorder = async () => {
    setIsLoading(true)
    try {
      const result = await reorder(orderId)
      // Current price + stock are re-resolved on the server; add what is available.
      result.items.forEach((item) => addItem(toProduct(item), item.quantity))
      if (result.skipped.length > 0) {
        const names = result.skipped.map((skipped) => skipped.product_name).join(', ')
        toast.warning(`Một số sản phẩm không còn khả dụng và đã được bỏ qua: ${names}`)
      }
      if (result.items.length === 0) {
        toast.error('Không còn sản phẩm nào từ đơn này để đặt lại.')
        return
      }
      toast.success('Đã thêm sản phẩm vào giỏ theo giá hiện tại.')
      router.push('/cart')
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Không thể đặt lại đơn này.')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <Button size="sm" variant="outline" disabled={isLoading} onClick={() => void handleReorder()}>
      <RotateCcw className="mr-2 h-4 w-4" />
      {isLoading ? 'Đang xử lý...' : 'Đặt lại'}
    </Button>
  )
}
