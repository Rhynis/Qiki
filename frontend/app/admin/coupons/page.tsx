'use client'

import { Plus } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { EmptyState } from '@/components/shared/empty-state'
import { PageHeader } from '@/components/shared/page-header'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import type { Coupon, CouponInput } from '@/lib/api/coupons'
import { useCoupons, useCreateCoupon, useUpdateCoupon } from '@/lib/hooks/use-coupons'
import { formatPrice } from '@/lib/utils/format'

const emptyForm: CouponInput = {
  code: '',
  discount_type: 'percent',
  value: '',
  min_order: '0',
  max_discount: '',
  usage_limit: null,
  per_user_limit: null,
  active: true,
}

export default function AdminCouponsPage() {
  const couponsQuery = useCoupons()
  const createMutation = useCreateCoupon()
  const updateMutation = useUpdateCoupon()
  const [createOpen, setCreateOpen] = useState(false)
  const [form, setForm] = useState<CouponInput>(emptyForm)

  async function handleCreate() {
    try {
      await createMutation.mutateAsync({
        code: form.code?.trim().toUpperCase(),
        discount_type: form.discount_type,
        value: form.value,
        min_order: form.min_order || '0',
        max_discount: form.max_discount ? form.max_discount : null,
        usage_limit: form.usage_limit ? Number(form.usage_limit) : null,
        per_user_limit: form.per_user_limit ? Number(form.per_user_limit) : null,
        active: true,
      })
      toast.success('Đã tạo mã giảm giá')
      setCreateOpen(false)
      setForm(emptyForm)
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Không thể tạo mã')
    }
  }

  async function toggleActive(coupon: Coupon) {
    try {
      await updateMutation.mutateAsync({ id: coupon.id, data: { active: !coupon.active } })
      toast.success(coupon.active ? 'Đã tắt mã' : 'Đã bật mã')
    } catch (caught) {
      toast.error(caught instanceof Error ? caught.message : 'Không thể cập nhật mã')
    }
  }

  const coupons = couponsQuery.data?.items ?? []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <PageHeader title="Mã giảm giá" description="Tạo và quản lý mã khuyến mãi." />
        <Button onClick={() => setCreateOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          Tạo mã
        </Button>
      </div>

      {coupons.length === 0 ? (
        <EmptyState title="Chưa có mã giảm giá" description="Tạo mã đầu tiên để bắt đầu khuyến mãi." />
      ) : (
        <div className="overflow-x-auto rounded-lg border bg-white">
          <table className="w-full text-sm">
            <thead className="border-b bg-slate-50 text-left text-slate-600">
              <tr>
                <th className="px-4 py-3">Mã</th>
                <th className="px-4 py-3">Loại</th>
                <th className="px-4 py-3">Giá trị</th>
                <th className="px-4 py-3">Đơn tối thiểu</th>
                <th className="px-4 py-3">Đã dùng</th>
                <th className="px-4 py-3">Trạng thái</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {coupons.map((coupon) => (
                <tr key={coupon.id} className="border-b last:border-0">
                  <td className="px-4 py-3 font-medium">{coupon.code}</td>
                  <td className="px-4 py-3">
                    {coupon.discount_type === 'percent' ? 'Phần trăm' : 'Cố định'}
                  </td>
                  <td className="px-4 py-3">
                    {coupon.discount_type === 'percent'
                      ? `${coupon.value}%`
                      : formatPrice(Number(coupon.value))}
                  </td>
                  <td className="px-4 py-3">{formatPrice(Number(coupon.min_order))}</td>
                  <td className="px-4 py-3">
                    {coupon.used_count}
                    {coupon.usage_limit ? ` / ${coupon.usage_limit}` : ''}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={
                        coupon.active ? 'font-medium text-emerald-700' : 'text-slate-400'
                      }
                    >
                      {coupon.active ? 'Đang bật' : 'Đã tắt'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={updateMutation.isPending}
                      onClick={() => void toggleActive(coupon)}
                    >
                      {coupon.active ? 'Tắt' : 'Bật'}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Tạo mã giảm giá</DialogTitle>
          </DialogHeader>
          <div className="space-y-3">
            <Field label="Mã">
              <input
                className={inputClass}
                value={form.code ?? ''}
                onChange={(event) => setForm((prev) => ({ ...prev, code: event.target.value }))}
                placeholder="VD: SALE10"
              />
            </Field>
            <Field label="Loại giảm">
              <select
                className={inputClass}
                value={form.discount_type}
                onChange={(event) =>
                  setForm((prev) => ({
                    ...prev,
                    discount_type: event.target.value as 'percent' | 'fixed',
                  }))
                }
              >
                <option value="percent">Phần trăm (%)</option>
                <option value="fixed">Số tiền cố định (đ)</option>
              </select>
            </Field>
            <Field label={form.discount_type === 'percent' ? 'Giá trị (%)' : 'Giá trị (đ)'}>
              <input
                className={inputClass}
                type="number"
                value={form.value ?? ''}
                onChange={(event) => setForm((prev) => ({ ...prev, value: event.target.value }))}
              />
            </Field>
            <Field label="Đơn tối thiểu (đ)">
              <input
                className={inputClass}
                type="number"
                value={form.min_order ?? ''}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, min_order: event.target.value }))
                }
              />
            </Field>
            <Field label="Giảm tối đa (đ, tùy chọn)">
              <input
                className={inputClass}
                type="number"
                value={form.max_discount ?? ''}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, max_discount: event.target.value }))
                }
              />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Giới hạn lượt (tùy chọn)">
                <input
                  className={inputClass}
                  type="number"
                  value={form.usage_limit ?? ''}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      usage_limit: event.target.value ? Number(event.target.value) : null,
                    }))
                  }
                />
              </Field>
              <Field label="Giới hạn/người (tùy chọn)">
                <input
                  className={inputClass}
                  type="number"
                  value={form.per_user_limit ?? ''}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      per_user_limit: event.target.value ? Number(event.target.value) : null,
                    }))
                  }
                />
              </Field>
            </div>
            <Button
              className="w-full"
              disabled={createMutation.isPending || !form.code?.trim() || !form.value}
              onClick={() => void handleCreate()}
            >
              {createMutation.isPending ? 'Đang tạo...' : 'Tạo mã'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

const inputClass =
  'h-10 w-full rounded-md border px-3 text-sm outline-none focus:ring-2 focus:ring-ring'

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label className="text-sm font-medium">{label}</label>
      {children}
    </div>
  )
}
