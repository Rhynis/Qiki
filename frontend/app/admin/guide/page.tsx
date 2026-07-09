'use client'

import {
  BookOpenText,
  ClipboardList,
  LayoutDashboard,
  MessageSquareText,
  Package,
  ShieldCheck,
  Users,
  type LucideIcon,
} from 'lucide-react'
import { PageHeader } from '@/components/shared/page-header'

/**
 * Staff/moderator handbook for the whole admin panel. Content is a plain data
 * structure so new sections/rules are easy to add without touching the render
 * logic. Handbook copy is Vietnamese (user-facing); the code stays English.
 */

type GuideBlock =
  | { kind: 'paragraph'; text: string }
  | { kind: 'list'; items: string[] }
  | { kind: 'definitions'; items: Array<{ term: string; description: string }> }

type GuideSection = {
  id: string
  title: string
  icon: LucideIcon
  summary: string
  blocks: GuideBlock[]
}

const sections: GuideSection[] = [
  {
    id: 'tong-quan',
    title: 'Tổng quan & phân quyền',
    icon: ShieldCheck,
    summary: 'Trang quản trị dành cho ai và điều hướng ra sao.',
    blocks: [
      {
        kind: 'paragraph',
        text: 'Trang quản trị (/admin) dành cho nhân viên và quản trị viên của Cửa hàng Gas Quốc Cường để theo dõi chat, xử lý đơn hàng, quản lý sản phẩm, kho tri thức và người dùng. Khách hàng thường không truy cập được khu vực này.',
      },
      {
        kind: 'definitions',
        items: [
          {
            term: 'Quản trị viên (admin)',
            description:
              'Toàn quyền: sản phẩm, đơn hàng, chat, kho tri thức, người dùng và dashboard.',
          },
          {
            term: 'Nhân viên (staff)',
            description:
              'Trực và trả lời chat, theo dõi đơn hàng. Không có các thao tác chỉ dành cho admin.',
          },
          {
            term: 'Khách hàng (customer)',
            description: 'Tài khoản mua hàng bình thường, không vào được trang quản trị.',
          },
        ],
      },
      {
        kind: 'paragraph',
        text: 'Thanh điều hướng bên trái gồm: Dashboard, Sản phẩm, Đơn hàng, Chat, Knowledge Base, Người dùng và trang Cẩm nang này.',
      },
    ],
  },
  {
    id: 'chat',
    title: 'Chat hỗ trợ (/admin/chat, /admin/chat/review)',
    icon: MessageSquareText,
    summary: 'Trạng thái, cờ cần chú ý, hàng đợi duyệt và cách xử lý cuộc trò chuyện.',
    blocks: [
      {
        kind: 'paragraph',
        text: 'Mỗi cuộc trò chuyện có một mã ngắn dạng CT-YYYYMMDD-NNN (ví dụ CT-20260709-001) để nhân viên dễ trao đổi, thay cho mã phiên UUID. Danh sách hiển thị mã, người/nội dung gần nhất, thời điểm (dd-mm-yyyy) và trạng thái.',
      },
      {
        kind: 'definitions',
        items: [
          { term: 'Đang hoạt động', description: 'Cuộc trò chuyện đang diễn ra bình thường.' },
          {
            term: 'Cần hỗ trợ',
            description: 'Đã chuyển cho nhân viên (escalated) — cần người thật vào trả lời.',
          },
          {
            term: 'Bị flag',
            description: 'Được đánh dấu để xem lại/theo dõi thêm.',
          },
          { term: 'Đã xử lý', description: 'Nhân viên đã giải quyết xong (resolved).' },
          {
            term: 'Đã kết thúc',
            description:
              'Đã đóng (closed). Cuộc trò chuyện không hoạt động quá 3 ngày sẽ tự động chuyển sang trạng thái này.',
          },
        ],
      },
      {
        kind: 'paragraph',
        text: 'Vì sao một cuộc trò chuyện bị gắn cờ để xem lại (hiển thị "Cần xem lại" ở tin nhắn và đếm vào ô "Bị flag"):',
      },
      {
        kind: 'list',
        items: [
          'Độ tự tin phân loại ý định thấp (intent_confidence < 0.6) — bot không chắc khách muốn gì.',
          'Khách chấm điểm phản hồi tiêu cực (feedback_score == -1) cho câu trả lời của bot.',
          'Tình huống an toàn khẩn cấp (rò rỉ, cháy nổ, ngạt khí) — đếm vào ô "Khẩn cấp" và hiện cảnh báo đỏ.',
        ],
      },
      {
        kind: 'paragraph',
        text: 'Các ô đếm ở đầu trang: "Cần hỗ trợ" (số cuộc đang escalated), "Khẩn cấp" (số cuộc có tin nhắn an toàn khẩn cấp), "Bị flag" (số cuộc có tin nhắn cần xem lại). Bộ lọc và ô tìm kiếm (theo mã, số điện thoại hoặc nội dung) giúp thu hẹp danh sách; không có dữ liệu nào bị xoá.',
      },
      {
        kind: 'paragraph',
        text: 'Trong màn hình chi tiết: đọc lịch sử tin nhắn (kèm thời gian), gõ trả lời khách trực tiếp, và dùng ô chọn trạng thái để đặt: Đang hoạt động, Cần hỗ trợ, Bị flag, Đã xử lý hoặc Đã kết thúc. Trang /admin/chat/review là hàng đợi các tin nhắn cần xem lại để soát nhanh.',
      },
    ],
  },
  {
    id: 'don-hang',
    title: 'Đơn hàng (/admin/orders)',
    icon: ClipboardList,
    summary: 'Mã đơn, trạng thái, phí giao hàng và các thao tác xác nhận/hủy.',
    blocks: [
      {
        kind: 'paragraph',
        text: 'Mỗi đơn có mã dạng GB-YYYYMMDD-NNNN (ví dụ GB-20260709-0001). Khách tra cứu đơn bằng mã này kèm số điện thoại.',
      },
      {
        kind: 'definitions',
        items: [
          {
            term: 'Chờ xác nhận (pending)',
            description: 'Đơn mới, có thể chuyển sang Đã xác nhận hoặc Đã hủy.',
          },
          {
            term: 'Đã xác nhận (confirmed)',
            description: 'Có thể chuyển sang Đang giao hoặc Đã hủy.',
          },
          { term: 'Đang giao (shipping)', description: 'Có thể chuyển sang Đã giao hoặc Đã hủy.' },
          { term: 'Đã giao (delivered)', description: 'Trạng thái cuối, không chuyển tiếp được.' },
          { term: 'Đã hủy (cancelled)', description: 'Trạng thái cuối, không chuyển tiếp được.' },
        ],
      },
      {
        kind: 'paragraph',
        text: 'Phí giao hàng: gas giao miễn phí; nước uống tính 5.000đ mỗi bình. Máy chủ luôn tự tính lại tổng tiền khi tạo đơn — số tóm tắt phía khách chỉ để hiển thị.',
      },
      {
        kind: 'paragraph',
        text: 'Xác nhận đơn khi đã kiểm tra thông tin và tồn kho; hủy đơn kèm lý do khi cần. Kho được trừ khi tạo đơn (khóa dòng để tránh bán quá số lượng).',
      },
    ],
  },
  {
    id: 'san-pham',
    title: 'Sản phẩm (/admin/products)',
    icon: Package,
    summary: 'Quản lý danh mục: hiển thị, tồn kho, biến thể và giá.',
    blocks: [
      {
        kind: 'definitions',
        items: [
          {
            term: 'Đang bán / Ngừng bán (is_active)',
            description:
              'Sản phẩm ngừng bán sẽ ẨN khỏi cửa hàng cho khách VÀ khỏi phần giá/tư vấn của Qiki. Dùng khi hết hàng dài hạn hoặc ngừng kinh doanh loại đó.',
          },
          {
            term: 'Tồn kho (stock)',
            description:
              'Số lượng còn bán; hết hàng sẽ được cảnh báo ở ô "Tồn kho thấp" trên dashboard.',
          },
          {
            term: 'Biến thể',
            description:
              'Cùng dung tích (ví dụ 12kg) có nhiều hãng và màu/loại với giá khác nhau — quản lý như các sản phẩm riêng (hãng/size/màu).',
          },
          {
            term: 'Giá (price)',
            description:
              'Giá bán nằm ở danh mục sản phẩm. Đây là nguồn giá duy nhất mà Qiki dùng khi báo giá.',
          },
        ],
      },
      {
        kind: 'paragraph',
        text: 'Lưu ý: giá KHÔNG đặt trong Kho tri thức. Khi đổi giá, chỉ cần sửa ở sản phẩm; Qiki sẽ dùng giá mới ngay.',
      },
    ],
  },
  {
    id: 'kho-tri-thuc',
    title: 'Kho tri thức (/admin/knowledge-base)',
    icon: BookOpenText,
    summary: 'Nội dung Qiki dùng để trả lời và mối quan hệ với danh mục sản phẩm.',
    blocks: [
      {
        kind: 'paragraph',
        text: 'Kho tri thức (KB) chứa các tài liệu về cửa hàng, chính sách, hướng dẫn an toàn, khu vực giao hàng… Qiki dùng RAG để tìm đoạn phù hợp trong KB rồi trả lời theo đó.',
      },
      {
        kind: 'paragraph',
        text: 'QUAN TRỌNG: giá sản phẩm KHÔNG lưu trong KB — giá đến từ danh mục sản phẩm (products). Không thêm bảng giá vào KB để tránh sai lệch khi giá thay đổi.',
      },
      {
        kind: 'paragraph',
        text: 'Khi thêm hoặc sửa tài liệu, hệ thống cần tạo lại embedding (re-embedding) thì nội dung mới mới được Qiki tìm thấy. Viết tài liệu rõ ràng, đúng thông tin cửa hàng.',
      },
    ],
  },
  {
    id: 'nguoi-dung',
    title: 'Người dùng (/admin/users)',
    icon: Users,
    summary: 'Vai trò và trạng thái hoạt động của tài khoản.',
    blocks: [
      {
        kind: 'paragraph',
        text: 'Danh sách người dùng có thể lọc theo vai trò (admin / staff / customer) và theo trạng thái hoạt động.',
      },
      {
        kind: 'definitions',
        items: [
          {
            term: 'Vai trò',
            description: 'admin (toàn quyền), staff (trực chat/đơn), customer (khách mua hàng).',
          },
          {
            term: 'Đang hoạt động / Vô hiệu hóa',
            description:
              'Tài khoản bị vô hiệu hóa không đăng nhập được cho tới khi được kích hoạt lại.',
          },
        ],
      },
    ],
  },
  {
    id: 'dashboard',
    title: 'Dashboard & chỉ số',
    icon: LayoutDashboard,
    summary: 'Ý nghĩa của từng ô số liệu.',
    blocks: [
      {
        kind: 'definitions',
        items: [
          { term: 'Đơn hôm nay', description: 'Số đơn được tạo trong ngày.' },
          { term: 'Đơn chờ xử lý', description: 'Số đơn đang ở trạng thái Chờ xác nhận.' },
          { term: 'Doanh thu hôm nay', description: 'Tổng tiền các đơn trong ngày.' },
          { term: 'Tồn kho thấp', description: 'Số sản phẩm sắp/đã hết cần nhập thêm.' },
          {
            term: 'Người dùng / Người dùng mới',
            description: 'Tổng số tài khoản và số mới gần đây.',
          },
          {
            term: 'Ô chat (Cần hỗ trợ / Khẩn cấp / Bị flag)',
            description: 'Đếm nhanh các cuộc trò chuyện cần chú ý (xem mục Chat).',
          },
        ],
      },
    ],
  },
]

function GuideBlockView({ block }: { block: GuideBlock }) {
  if (block.kind === 'paragraph') {
    return <p className="text-sm leading-6 text-slate-700">{block.text}</p>
  }
  if (block.kind === 'list') {
    return (
      <ul className="list-disc space-y-1 pl-5 text-sm leading-6 text-slate-700">
        {block.items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    )
  }
  return (
    <dl className="space-y-2">
      {block.items.map((item) => (
        <div key={item.term} className="text-sm leading-6">
          <dt className="font-semibold text-slate-900">{item.term}</dt>
          <dd className="text-slate-700">{item.description}</dd>
        </div>
      ))}
    </dl>
  )
}

export default function AdminGuidePage() {
  return (
    <section className="space-y-6">
      <PageHeader
        title="Cẩm nang quản trị"
        description="Hướng dẫn toàn bộ trang quản trị cho nhân viên và quản trị viên."
      />

      <nav className="rounded-lg border bg-white p-4">
        <p className="mb-2 text-sm font-medium text-slate-600">Mục lục</p>
        <ul className="grid gap-1 sm:grid-cols-2">
          {sections.map((section) => (
            <li key={section.id}>
              <a
                href={`#${section.id}`}
                className="inline-flex items-center gap-2 text-sm text-primary hover:underline"
              >
                <section.icon className="h-4 w-4" />
                {section.title}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      {sections.map((section) => (
        <article
          key={section.id}
          id={section.id}
          className="scroll-mt-20 space-y-3 rounded-lg border bg-white p-5"
        >
          <div className="flex items-center gap-2">
            <section.icon className="h-5 w-5 text-primary" />
            <h2 className="text-lg font-semibold text-slate-900">{section.title}</h2>
          </div>
          <p className="text-sm text-slate-500">{section.summary}</p>
          <div className="space-y-3">
            {section.blocks.map((block, index) => (
              <GuideBlockView key={index} block={block} />
            ))}
          </div>
        </article>
      ))}
    </section>
  )
}
