import { Pencil, Trash2 } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { formatPrice, formatProductSize } from '@/lib/utils/format'
import type { Product } from '@/types/product'

type ProductTableProps = {
  products: Product[]
  onEdit: (product: Product) => void
  onDelete: (product: Product) => void
}

export function ProductTable({ products, onEdit, onDelete }: ProductTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Sản phẩm</TableHead>
          <TableHead>SKU</TableHead>
          <TableHead>Giá</TableHead>
          <TableHead>Tồn kho</TableHead>
          <TableHead>Trạng thái</TableHead>
          <TableHead className="text-right">Thao tác</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {products.map((product) => (
          <TableRow key={product.id}>
            <TableCell>
              <div className="font-medium">{product.name}</div>
              <div className="text-sm text-slate-600">
                {product.brand} · {formatProductSize(product.size_kg, product.unit)}
              </div>
            </TableCell>
            <TableCell>{product.sku}</TableCell>
            <TableCell>{formatPrice(product.price)}</TableCell>
            <TableCell>{product.stock_quantity.toLocaleString('vi-VN')}</TableCell>
            <TableCell>
              <Badge variant={product.is_active ? 'default' : 'outline'}>
                {product.is_active ? 'Đang bán' : 'Đã ẩn'}
              </Badge>
            </TableCell>
            <TableCell className="text-right">
              <div className="flex justify-end gap-2">
                <Button variant="outline" size="icon" onClick={() => onEdit(product)}>
                  <Pencil className="h-4 w-4" />
                  <span className="sr-only">Sửa</span>
                </Button>
                <Button variant="outline" size="icon" onClick={() => onDelete(product)}>
                  <Trash2 className="h-4 w-4" />
                  <span className="sr-only">Ẩn</span>
                </Button>
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
