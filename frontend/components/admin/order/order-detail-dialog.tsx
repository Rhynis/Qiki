'use client'

import { OrderStatusUpdater } from '@/components/admin/order/order-status-updater'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useIssueInvoice } from '@/lib/hooks/use-orders'
import { formatDate, formatPhone, formatPrice } from '@/lib/utils/format'
import type { Order, OrderStatus, PaymentMethod, PaymentStatus } from '@/types/order'

const statusLabels: Record<OrderStatus, string> = {
  pending: 'Chờ xác nhận',
  confirmed: 'Đã xác nhận',
  shipping: 'Đang giao',
  delivered: 'Đã giao',
  cancelled: 'Đã hủy',
}

const paymentMethodLabels: Record<PaymentMethod, string> = {
  cod: 'Tiền mặt khi nhận hàng (COD)',
  bank_transfer: 'Chuyển khoản ngân hàng',
}

const paymentStatusLabels: Record<PaymentStatus, string> = {
  pending: 'Chưa thanh toán',
  paid: 'Đã thanh toán',
  refunded: 'Đã hoàn tiền',
}

const sourceLabels: Record<string, string> = {
  website: 'Website',
  chatbot: 'Chat Qiki',
}

type OrderDetailDialogProps = {
  order: Order | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function OrderDetailDialog({ order, open, onOpenChange }: OrderDetailDialogProps) {
  const issueInvoice = useIssueInvoice()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
        {order ? (
          <>
            <DialogHeader>
              <DialogTitle className="flex flex-wrap items-center gap-2">
                Đơn {order.order_number}
                <Badge variant="outline">{statusLabels[order.status] ?? order.status}</Badge>
              </DialogTitle>
              <DialogDescription>
                Đặt lúc {formatDate(order.created_at)} ·{' '}
                {sourceLabels[order.source] ?? order.source}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-5 text-sm">
              <section className="grid gap-4 sm:grid-cols-2">
                <DetailBlock title="Khách hàng">
                  <p className="font-medium text-slate-900">{order.customer_name}</p>
                  <p className="text-slate-600">{formatPhone(order.customer_phone)}</p>
                  {order.customer_email ? (
                    <p className="text-slate-600">{order.customer_email}</p>
                  ) : null}
                </DetailBlock>
                <DetailBlock title="Thanh toán">
                  <p className="text-slate-900">
                    {paymentMethodLabels[order.payment_method] ?? order.payment_method}
                  </p>
                  <p className="text-slate-600">
                    {paymentStatusLabels[order.payment_status] ?? order.payment_status}
                  </p>
                </DetailBlock>
              </section>

              <DetailBlock title="Giao hàng">
                <p className="text-slate-900">{order.delivery_address}</p>
                <p className="text-slate-600">
                  {[order.delivery_ward, order.delivery_district, order.delivery_city]
                    .filter(Boolean)
                    .join(', ')}
                </p>
                {order.delivery_notes ? (
                  <p className="mt-1 text-slate-600">Ghi chú: {order.delivery_notes}</p>
                ) : null}
                {order.different_recipient_name ? (
                  <p className="mt-1 text-slate-600">
                    Người nhận khác: {order.different_recipient_name}
                    {order.different_recipient_phone
                      ? ` · ${formatPhone(order.different_recipient_phone)}`
                      : ''}
                  </p>
                ) : null}
              </DetailBlock>

              <DetailBlock title="Sản phẩm">
                <div className="overflow-x-auto rounded-md border">
                  <table className="w-full min-w-[420px] text-left text-sm">
                    <thead className="bg-slate-100 text-slate-600">
                      <tr>
                        <th className="p-2 font-medium">Sản phẩm</th>
                        <th className="p-2 text-right font-medium">SL</th>
                        <th className="p-2 text-right font-medium">Đơn giá</th>
                        <th className="p-2 text-right font-medium">Thành tiền</th>
                      </tr>
                    </thead>
                    <tbody>
                      {order.items.map((item) => (
                        <tr key={item.id} className="border-t">
                          <td className="p-2">
                            <p className="font-medium text-slate-900">{item.product_name}</p>
                            <p className="text-xs text-slate-500">
                              {[
                                item.product_brand,
                                item.product_size_kg ? `${item.product_size_kg} kg` : null,
                              ]
                                .filter(Boolean)
                                .join(' · ')}
                              {item.is_exchange ? ' · đổi vỏ' : ''}
                            </p>
                          </td>
                          <td className="p-2 text-right">{item.quantity}</td>
                          <td className="p-2 text-right">{formatPrice(item.unit_price)}</td>
                          <td className="p-2 text-right">{formatPrice(item.subtotal)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <dl className="mt-3 space-y-1">
                  <SummaryRow label="Tạm tính" value={formatPrice(order.subtotal)} />
                  <SummaryRow label="Phí giao hàng" value={formatPrice(order.shipping_fee)} />
                  <SummaryRow label="Tổng cộng" value={formatPrice(order.total_amount)} emphasize />
                </dl>
              </DetailBlock>

              {order.customer_notes || order.internal_notes ? (
                <DetailBlock title="Ghi chú">
                  {order.customer_notes ? (
                    <p className="text-slate-600">Khách: {order.customer_notes}</p>
                  ) : null}
                  {order.internal_notes ? (
                    <p className="text-slate-600">Nội bộ: {order.internal_notes}</p>
                  ) : null}
                </DetailBlock>
              ) : null}

              <DetailBlock title="Trạng thái">
                <dl className="space-y-1">
                  <SummaryRow label="Cập nhật gần nhất" value={formatDate(order.updated_at)} />
                  {order.delivered_at ? (
                    <SummaryRow label="Đã giao lúc" value={formatDate(order.delivered_at)} />
                  ) : null}
                  {order.cancelled_at ? (
                    <SummaryRow label="Đã hủy lúc" value={formatDate(order.cancelled_at)} />
                  ) : null}
                  {order.cancelled_reason ? (
                    <SummaryRow label="Lý do hủy" value={order.cancelled_reason} />
                  ) : null}
                </dl>
                <div className="mt-3 flex items-center gap-2">
                  <span className="text-slate-600">Đổi trạng thái:</span>
                  <OrderStatusUpdater order={order} />
                </div>
              </DetailBlock>

              <DetailBlock title="Hóa đơn điện tử">
                {order.einvoice ? (
                  <p className="text-slate-700">
                    Trạng thái: {order.einvoice.status}
                    {order.einvoice.invoice_no ? ` · Số ${order.einvoice.invoice_no}` : ''}
                  </p>
                ) : (
                  <p className="text-slate-500">Chưa xuất hóa đơn.</p>
                )}
                {order.status === 'delivered' ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    className="mt-2"
                    disabled={issueInvoice.isPending}
                    onClick={() => issueInvoice.mutate(order.id)}
                  >
                    Xuất hóa đơn điện tử
                  </Button>
                ) : (
                  <p className="text-xs text-slate-500">
                    Chỉ xuất hóa đơn được cho đơn đã giao.
                  </p>
                )}
              </DetailBlock>
            </div>
          </>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}

function DetailBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-1">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</p>
      {children}
    </section>
  )
}

function SummaryRow({
  label,
  value,
  emphasize = false,
}: {
  label: string
  value: string
  emphasize?: boolean
}) {
  return (
    <div className="flex items-center justify-between">
      <dt className="text-slate-600">{label}</dt>
      <dd className={emphasize ? 'font-semibold text-slate-900' : 'text-slate-900'}>{value}</dd>
    </div>
  )
}
