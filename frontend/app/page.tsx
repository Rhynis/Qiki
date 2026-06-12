import Link from 'next/link'
import {
  Bot,
  CheckCircle2,
  Clock,
  Headphones,
  MapPin,
  Phone,
  ShieldCheck,
  ShoppingBag,
  Truck,
} from 'lucide-react'
import { ChatOpenButton } from '@/components/shared/chat-open-button'
import { DeliveryAreaPopover } from '@/components/shared/delivery-area-popover'
import { StoreStatusBadge } from '@/components/shared/store-status-badge'
import { Button } from '@/components/ui/button'
import { SHOP_INFO } from '@/lib/constants'
import { protectVi } from '@/lib/utils'

const trustItems = [
  {
    title: 'Qiki AI 24/7',
    description: 'Hỏi giá, chọn bình, kiểm tra khu vực giao và tạo đơn ngay trong chat.',
    icon: Bot,
  },
  {
    title: 'Giao tận nơi theo giờ',
    description: [
      `${SHOP_INFO.hours.weekdaysLabel}: ${SHOP_INFO.hours.weekdaysTime}`,
      `${SHOP_INFO.hours.weekendsLabel}: ${SHOP_INFO.hours.weekendsTime}`,
    ],
    icon: Clock,
  },
  {
    title: 'An toàn, chính hãng',
    description: 'Bình còn niêm phong, hỗ trợ lắp van và kiểm tra rò rỉ khi giao.',
    icon: ShieldCheck,
  },
  {
    title: 'Phục vụ đúng khu vực',
    description: `Ưu tiên tuyến ${SHOP_INFO.deliveryAreaLabel} để giao nhanh và xác nhận rõ ràng.`,
    icon: MapPin,
  },
]

const orderSteps = [
  {
    title: 'Chọn sản phẩm hoặc nhắn Qiki',
    description:
      'Tự xem ở trang sản phẩm, thêm vào giỏ rồi thanh toán; hoặc nhờ trợ lý ảo Qiki tư vấn và chốt đơn ngay trong chat.',
    icon: ShoppingBag,
  },
  {
    title: 'Nhân viên gọi xác nhận',
    description: 'Cửa hàng kiểm tra thương hiệu, địa chỉ, thời gian giao và tổng chi phí.',
    icon: Headphones,
  },
  {
    title: 'Giao tận nơi, thu tiền khi nhận',
    description:
      'Nhân viên giao bình, lắp đặt nếu cần, lấy vỏ bình cũ và nhận thanh toán: tiền mặt khi giao hoặc chuyển khoản ngân hàng.',
    icon: Truck,
  },
]

const heroDetails: Array<{ label: string; value: string }> = [
  { label: 'Hotline/Zalo', value: SHOP_INFO.hotline.label },
  { label: 'Giờ mở cửa', value: SHOP_INFO.hours.summary },
  {
    label: 'Thanh toán',
    value: 'Tiền mặt khi nhận hàng (COD) hoặc chuyển khoản ngân hàng',
  },
]

export default function HomePage() {
  return (
    <div className="bg-slate-50">
      <section className="bg-slate-950 text-white">
        <div className="mx-auto max-w-6xl px-4 py-12 md:py-16">
          <div className="grid gap-10 md:grid-cols-[1.08fr_0.92fr] md:items-center">
            <div className="space-y-7">
              <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1 text-sm text-slate-200">
                <CheckCircle2 className="h-4 w-4 text-primary" />
                Giao nhanh tận nơi {protectVi(SHOP_INFO.deliveryAreaLabel)}
              </div>
              <div className="space-y-4">
                <h1 className="max-w-3xl text-4xl font-semibold text-white md:text-5xl">
                  {protectVi('Đặt gas LPG nhanh, ')}
                  <br className="hidden md:block" />
                  {protectVi('rõ giá, có trợ lý ảo Qiki ')}
                  <br className="hidden md:block" />
                  {protectVi('hỗ trợ từng bước')}
                </h1>
                <p className="max-w-2xl text-lg text-slate-300">
                  {protectVi(
                    'Gas Quốc Cường giao bình gas gia đình và kinh doanh tại Bình Thạnh & Thủ Đức, nhận đơn qua chat, hotline và Zalo trong giờ mở cửa.'
                  )}
                </p>
              </div>
              <div className="flex w-full max-w-md flex-col gap-3 sm:max-w-none sm:flex-row sm:flex-wrap sm:items-start">
                <div className="flex w-full flex-col gap-3 sm:w-auto">
                  <ChatOpenButton className="w-full bg-primary text-primary-foreground hover:bg-primary/90" />
                  <Button
                    asChild
                    className="w-full border-white/40 bg-white/5 text-white hover:bg-white/10 hover:text-white"
                    size="lg"
                    variant="outline"
                  >
                    <Link href="/products">Xem sản phẩm</Link>
                  </Button>
                </div>
                <Button
                  asChild
                  className="w-full border-transparent bg-white text-slate-950 hover:bg-slate-100 sm:w-auto"
                  size="lg"
                  variant="outline"
                >
                  <a href={SHOP_INFO.hotline.href}>
                    <Phone className="h-4 w-4" />
                    Gọi đặt: {SHOP_INFO.hotline.label}
                  </a>
                </Button>
              </div>
            </div>

            <div className="rounded-lg border border-white/10 bg-white/[0.06] p-5 shadow-2xl shadow-slate-950/40">
              <div className="rounded-md border border-white/10 bg-slate-900 p-4">
                <div className="border-b border-white/10 pb-4">
                  <div className="flex items-start justify-between gap-3">
                    <p className="text-sm text-slate-400">Khu vực giao hàng</p>
                    <StoreStatusBadge className="shrink-0 px-3 py-1 text-sm" variant="dark" />
                  </div>
                  <div className="mt-1.5 flex items-center gap-2">
                    <p className="text-xl font-semibold leading-tight text-white">
                      {protectVi('Bình Thạnh & Thủ Đức')}
                    </p>
                    <DeliveryAreaPopover />
                  </div>
                </div>
                <div className="mt-5 grid gap-3">
                  {heroDetails.map(({ label, value }) => (
                    <div
                      className="flex items-center justify-between gap-4 rounded-md bg-white/[0.06] px-4 py-3"
                      key={label}
                    >
                      <span className="text-sm text-slate-400">{label}</span>
                      <span className="text-right text-sm font-semibold text-white">
                        {protectVi(value)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-10">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {trustItems.map((item) => (
            <div className="rounded-lg border bg-white p-5 shadow-sm" key={item.title}>
              <item.icon className="h-6 w-6 text-primary" />
              <h2 className="mt-4 text-lg font-semibold text-slate-950">{item.title}</h2>
              {Array.isArray(item.description) ? (
                <div className="mt-2 space-y-1 text-sm text-slate-600">
                  {item.description.map((line) => (
                    <p key={line}>{protectVi(line)}</p>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-sm text-slate-600">{protectVi(item.description)}</p>
              )}
            </div>
          ))}
        </div>
      </section>

      <section className="border-y bg-white">
        <div className="mx-auto max-w-6xl px-4 py-12">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
            <div>
              <h2 className="text-3xl font-semibold text-slate-950">Cách đặt hàng</h2>
              <p className="mt-2 max-w-2xl text-slate-600">
                {protectVi(
                  'Quy trình phù hợp cả khách quen gọi đổi bình nhanh và khách mới cần Qiki tư vấn trước khi đặt.'
                )}
              </p>
            </div>
            <Button asChild variant="outline">
              <a href={SHOP_INFO.zalo.href} rel="noreferrer" target="_blank">
                Nhắn Zalo
              </a>
            </Button>
          </div>
          <div className="mt-8 grid gap-4 md:grid-cols-3">
            {orderSteps.map((step, index) => (
              <div
                className="flex h-full flex-col rounded-lg border border-slate-200 bg-slate-50 p-5"
                key={step.title}
              >
                <div className="flex items-center justify-between">
                  <span className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                    {index + 1}
                  </span>
                  <step.icon className="h-5 w-5 text-slate-400" />
                </div>
                <h3 className="mt-4 text-lg font-semibold text-slate-950">
                  {protectVi(step.title)}
                </h3>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  {protectVi(step.description)}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12">
        <div className="rounded-lg border bg-slate-950 p-6 text-white md:flex md:items-center md:justify-between md:gap-8">
          <div>
            <p className="text-sm font-medium text-primary">Cần đổi gas gấp?</p>
            <h2 className="mt-2 text-2xl font-semibold">
              Gọi cửa hàng để kiểm tra tuyến giao gần nhất
            </h2>
            <p className="mt-2 max-w-2xl text-sm text-slate-300">
              Nhân viên sẽ xác nhận sản phẩm còn hàng, địa chỉ thuộc khu vực giao và thời gian đến
              dự kiến trước khi chốt đơn.
            </p>
          </div>
          <div className="mt-5 flex flex-col gap-3 sm:flex-row md:mt-0">
            <Button asChild className="bg-primary text-primary-foreground hover:bg-primary/90">
              <a href={SHOP_INFO.hotline.href}>Gọi {SHOP_INFO.hotline.label}</a>
            </Button>
            <Button
              asChild
              className="border-white/40 bg-white/5 text-white hover:bg-white/10 hover:text-white"
              variant="outline"
            >
              <Link href="/track">Tra cứu đơn</Link>
            </Button>
          </div>
        </div>
      </section>
    </div>
  )
}
