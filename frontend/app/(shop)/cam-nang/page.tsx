import Link from 'next/link'
import { ArrowRight } from 'lucide-react'
import type { Metadata } from 'next'
import { getArticlesByCategory } from '@/lib/content/cam-nang'

// Serve the guide index from the ISR cache (revalidated every 60s), mirroring the
// products route so a repeat visit renders instantly instead of re-reading content.
export const revalidate = 60

export const metadata: Metadata = {
  title: 'Cẩm nang gas & nước uống',
  description:
    'Kiến thức về gas LPG, an toàn sử dụng, thương hiệu và nước uống đóng bình — hướng dẫn dễ hiểu cho gia đình.',
}

export default function CamNangIndexPage() {
  const groups = getArticlesByCategory()

  return (
    <section className="mx-auto max-w-6xl space-y-10 px-4 py-8">
      <header className="space-y-2">
        <h1 className="text-3xl font-semibold text-slate-950 md:text-4xl">Cẩm nang</h1>
        <p className="max-w-2xl text-slate-600">
          Kiến thức về gas LPG, an toàn sử dụng, các thương hiệu và nước uống đóng bình — tổng hợp
          ngắn gọn, dễ áp dụng cho gia đình bạn.
        </p>
      </header>

      {groups.map((group) => (
        <div key={group.category} className="space-y-4">
          <h2 className="text-xl font-semibold text-slate-950">{group.label}</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {group.articles.map((article) => (
              <Link
                key={article.slug}
                href={`/cam-nang/${article.slug}`}
                className="group flex h-full flex-col rounded-xl border border-slate-200 p-5 transition hover:border-primary/50 hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <h3 className="font-semibold text-slate-950 group-hover:text-primary">
                  {article.title}
                </h3>
                <p className="mt-2 line-clamp-3 flex-1 text-sm text-slate-600">{article.summary}</p>
                <span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary">
                  Đọc tiếp
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                </span>
              </Link>
            ))}
          </div>
        </div>
      ))}
    </section>
  )
}
