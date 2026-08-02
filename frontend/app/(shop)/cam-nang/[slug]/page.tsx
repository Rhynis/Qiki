import Link from 'next/link'
import { notFound } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'
import type { Metadata } from 'next'
import { MarkdownContent } from '@/components/shop/markdown-content'
import { getAllSlugs, getArticleBySlug } from '@/lib/content/cam-nang'

// Pre-render every article at build time; refresh from the ISR cache every 60s to
// stay in step with the index route.
export const revalidate = 60

type ArticlePageProps = {
  params: Promise<{ slug: string }>
}

export function generateStaticParams(): { slug: string }[] {
  return getAllSlugs().map((slug) => ({ slug }))
}

export async function generateMetadata({ params }: ArticlePageProps): Promise<Metadata> {
  const { slug } = await params
  const article = getArticleBySlug(slug)
  if (!article) return {}
  return {
    title: article.title,
    description: article.summary,
  }
}

export default async function CamNangArticlePage({ params }: ArticlePageProps) {
  const { slug } = await params
  const article = getArticleBySlug(slug)
  if (!article) notFound()

  return (
    <article className="mx-auto max-w-3xl space-y-6 px-4 py-8">
      <Link
        href="/cam-nang"
        className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 transition hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ArrowLeft className="h-4 w-4" />
        Về Cẩm nang
      </Link>

      <header className="space-y-3 border-b border-slate-200 pb-6">
        <h1 className="text-3xl font-semibold text-slate-950 md:text-4xl">{article.title}</h1>
        <p className="text-slate-600">{article.summary}</p>
      </header>

      <MarkdownContent content={article.content} />
    </article>
  )
}
