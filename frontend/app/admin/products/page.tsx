'use client'

import { Plus } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { LowStockAlert } from '@/components/admin/product/low-stock-alert'
import { ProductForm } from '@/components/admin/product/product-form'
import { ProductTable } from '@/components/admin/product/product-table'
import { EmptyState } from '@/components/shared/empty-state'
import { PageHeader } from '@/components/shared/page-header'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useAuth } from '@/lib/hooks/use-auth'
import {
  useCreateProduct,
  useDeleteProduct,
  useLowStockProducts,
  useProducts,
  useUpdateProduct,
} from '@/lib/hooks/use-products'
import type { Product, ProductCreateInput, ProductUpdateInput } from '@/types/product'

export default function AdminProductsPage() {
  const { isAdmin, isLoading } = useAuth()
  const [createOpen, setCreateOpen] = useState(false)
  const [editingProduct, setEditingProduct] = useState<Product | null>(null)
  const productsQuery = useProducts({ limit: 100, sort_by: 'created_at', sort_order: 'desc' })
  const lowStockQuery = useLowStockProducts(10)
  const createMutation = useCreateProduct()
  const updateMutation = useUpdateProduct()
  const deleteMutation = useDeleteProduct()

  async function handleCreate(data: ProductCreateInput | ProductUpdateInput) {
    try {
      await createMutation.mutateAsync(data as ProductCreateInput)
      setCreateOpen(false)
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Không thể tạo sản phẩm')
    }
  }

  async function handleUpdate(data: ProductCreateInput | ProductUpdateInput) {
    if (!editingProduct) return
    try {
      await updateMutation.mutateAsync({ productId: editingProduct.id, data })
      setEditingProduct(null)
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Không thể cập nhật sản phẩm')
    }
  }

  async function handleDelete(product: Product) {
    if (!window.confirm(`Ẩn sản phẩm ${product.name}?`)) return
    try {
      await deleteMutation.mutateAsync(product.id)
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Không thể ẩn sản phẩm')
    }
  }

  if (!isLoading && !isAdmin) {
    return (
      <section className="mx-auto max-w-6xl px-4 py-8">
        <EmptyState
          title="Không có quyền truy cập"
          description="Khu vực này dành cho quản trị viên."
        />
      </section>
    )
  }

  const products = productsQuery.data?.items ?? []
  const lowStockCount = lowStockQuery.data?.length ?? 0

  return (
    <section className="mx-auto max-w-6xl space-y-6 px-4 py-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <PageHeader
          title="Quản lý sản phẩm"
          description="Tạo, cập nhật và theo dõi tồn kho sản phẩm gas LPG."
        />
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Thêm sản phẩm
        </Button>
      </div>

      <LowStockAlert count={lowStockCount} />

      <div className="rounded-lg border bg-white">
        <ProductTable
          products={products}
          onEdit={setEditingProduct}
          onDelete={(product) => void handleDelete(product)}
        />
        {products.length === 0 ? (
          <div className="p-6">
            <EmptyState
              title="Chưa có sản phẩm"
              description="Tạo sản phẩm đầu tiên để bắt đầu bán hàng."
            />
          </div>
        ) : null}
      </div>

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Thêm sản phẩm</DialogTitle>
            <DialogDescription>
              Thông tin này sẽ hiển thị trong catalog khách hàng.
            </DialogDescription>
          </DialogHeader>
          <ProductForm isSubmitting={createMutation.isPending} onSubmit={handleCreate} />
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(editingProduct)}
        onOpenChange={(open) => !open && setEditingProduct(null)}
      >
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Sửa sản phẩm</DialogTitle>
            <DialogDescription>Cập nhật thông tin và trạng thái bán hàng.</DialogDescription>
          </DialogHeader>
          {editingProduct ? (
            <ProductForm
              key={editingProduct.id}
              product={editingProduct}
              isSubmitting={updateMutation.isPending}
              onSubmit={handleUpdate}
            />
          ) : null}
        </DialogContent>
      </Dialog>
    </section>
  )
}
