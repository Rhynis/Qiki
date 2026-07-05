'use client'

import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useAuth } from '@/lib/hooks/use-auth'
import { useCheckoutStore } from '@/lib/stores/checkout-store'
import { customerDeliverySchema } from '@/lib/validations/order'
import {
  deliveryWardGroups,
  getDeliveryZoneByWard,
  vietnameseAddresses,
} from '@/utils/vietnamese-address'

function issueMap(error: unknown): Record<string, string> {
  if (!error || typeof error !== 'object' || !('issues' in error)) return {}
  const issues = (error as { issues: Array<{ path: Array<string | number>; message: string }> })
    .issues
  return Object.fromEntries(issues.map((issue) => [issue.path.join('.'), issue.message]))
}

export function CustomerDeliveryStep({ onNext }: { onNext: () => void }) {
  const { user } = useAuth()
  const form = useCheckoutStore((state) => state.form)
  const updateForm = useCheckoutStore((state) => state.updateForm)
  const previousStep = useCheckoutStore((state) => state.previousStep)
  const [errors, setErrors] = useState<Record<string, string>>({})

  useEffect(() => {
    if (!user) return
    // Prefill from the saved account profile, but only fields the user has not
    // already filled, so an in-progress edit is never overwritten.
    const prefilledWard = form.delivery_ward || user.delivery_ward || ''
    updateForm({
      customer_name: form.customer_name || user.full_name || '',
      customer_phone: form.customer_phone || user.phone || '',
      customer_email: form.customer_email || user.email || '',
      delivery_address: form.delivery_address || user.address || '',
      delivery_ward: prefilledWard,
      delivery_district: form.delivery_district || getDeliveryZoneByWard(prefilledWard) || '',
      delivery_city: form.delivery_city || user.delivery_city || '',
      delivery_notes: form.delivery_notes || user.delivery_notes || '',
    })
  }, [
    form.customer_email,
    form.customer_name,
    form.customer_phone,
    form.delivery_address,
    form.delivery_city,
    form.delivery_district,
    form.delivery_notes,
    form.delivery_ward,
    updateForm,
    user,
  ])

  const submit = () => {
    const result = customerDeliverySchema.safeParse(form)
    if (!result.success) {
      setErrors(issueMap(result.error))
      return
    }
    setErrors({})
    onNext()
  }

  return (
    <div className="space-y-5 rounded-lg border bg-white p-5">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="customer_name">Họ tên</Label>
          <Input
            id="customer_name"
            value={form.customer_name}
            onChange={(event) => updateForm({ customer_name: event.target.value })}
          />
          {errors.customer_name ? (
            <p className="text-sm text-red-700">{errors.customer_name}</p>
          ) : null}
        </div>
        <div className="space-y-2">
          <Label htmlFor="customer_phone">Số điện thoại</Label>
          <Input
            id="customer_phone"
            value={form.customer_phone}
            onChange={(event) => updateForm({ customer_phone: event.target.value })}
          />
          {errors.customer_phone ? (
            <p className="text-sm text-red-700">{errors.customer_phone}</p>
          ) : null}
        </div>
        <div className="space-y-2 md:col-span-2">
          <Label htmlFor="customer_email">Email</Label>
          <Input
            id="customer_email"
            value={form.customer_email}
            onChange={(event) => updateForm({ customer_email: event.target.value })}
          />
          {errors.customer_email ? (
            <p className="text-sm text-red-700">{errors.customer_email}</p>
          ) : null}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="delivery_city">Tỉnh/thành</Label>
          <select
            id="delivery_city"
            className="h-10 w-full rounded-md border bg-white px-3 text-sm"
            value={form.delivery_city}
            onChange={(event) =>
              updateForm({
                delivery_city: event.target.value,
                delivery_district: '',
                delivery_ward: '',
              })
            }
          >
            {vietnameseAddresses.map((province) => (
              <option key={province.name} value={province.name}>
                {province.name}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="delivery_ward">Phường/xã</Label>
          <select
            id="delivery_ward"
            className="h-10 w-full rounded-md border bg-white px-3 text-sm"
            value={form.delivery_ward}
            onChange={(event) =>
              updateForm({
                delivery_ward: event.target.value,
                delivery_district: getDeliveryZoneByWard(event.target.value) ?? '',
              })
            }
          >
            <option value="">Chọn phường/xã</option>
            {deliveryWardGroups.map((group) => (
              <optgroup key={group.name} label={group.name}>
                {group.wards.map((ward) => (
                  <option key={ward.name} value={ward.name}>
                    {ward.name}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
          {errors.delivery_ward ? (
            <p className="text-sm text-red-700">{errors.delivery_ward}</p>
          ) : null}
        </div>
        <div className="space-y-2 md:col-span-2">
          <Label htmlFor="delivery_address">Địa chỉ</Label>
          <Input
            id="delivery_address"
            value={form.delivery_address}
            onChange={(event) => updateForm({ delivery_address: event.target.value })}
          />
          {errors.delivery_address ? (
            <p className="text-sm text-red-700">{errors.delivery_address}</p>
          ) : null}
        </div>
        <div className="space-y-2 md:col-span-2">
          <Label htmlFor="delivery_notes">Ghi chú giao hàng</Label>
          <Textarea
            id="delivery_notes"
            value={form.delivery_notes}
            onChange={(event) => updateForm({ delivery_notes: event.target.value })}
          />
        </div>
      </div>

      <label className="flex items-center gap-2 text-sm font-medium">
        <Checkbox
          checked={form.has_different_recipient}
          onCheckedChange={(checked) => updateForm({ has_different_recipient: checked === true })}
        />
        Người nhận khác
      </label>
      {form.has_different_recipient ? (
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="different_recipient_name">Tên người nhận</Label>
            <Input
              id="different_recipient_name"
              value={form.different_recipient_name}
              onChange={(event) => updateForm({ different_recipient_name: event.target.value })}
            />
            {errors.different_recipient_name ? (
              <p className="text-sm text-red-700">{errors.different_recipient_name}</p>
            ) : null}
          </div>
          <div className="space-y-2">
            <Label htmlFor="different_recipient_phone">SĐT người nhận</Label>
            <Input
              id="different_recipient_phone"
              value={form.different_recipient_phone}
              onChange={(event) => updateForm({ different_recipient_phone: event.target.value })}
            />
            {errors.different_recipient_phone ? (
              <p className="text-sm text-red-700">{errors.different_recipient_phone}</p>
            ) : null}
          </div>
        </div>
      ) : null}

      <div className="flex justify-between">
        <Button type="button" variant="outline" onClick={previousStep}>
          Quay lại
        </Button>
        <Button type="button" onClick={submit}>
          Tiếp tục
        </Button>
      </div>
    </div>
  )
}
