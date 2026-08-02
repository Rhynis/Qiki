import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import CamNangIndexPage from '@/app/(shop)/cam-nang/page'
import { MarkdownContent } from '@/components/shop/markdown-content'
import { CAM_NANG_CATEGORIES, getAllArticles, getArticleBySlug } from '@/lib/content/cam-nang'

// The five seeded articles that ship on main under frontend/content/cam-nang.
const SEEDED_SLUGS = [
  'an-toan-su-dung-gas',
  'kien-thuc-ve-gas-lpg',
  'chon-va-doi-binh-gas',
  'cac-thuong-hieu-gas',
  'nuoc-uong-dong-binh',
]

describe('cam-nang content loader', () => {
  it('reads every seeded article with parsed frontmatter', () => {
    const articles = getAllArticles()
    const slugs = articles.map((article) => article.slug)

    for (const slug of SEEDED_SLUGS) {
      expect(slugs).toContain(slug)
    }
    for (const article of articles) {
      expect(article.title).not.toBe('')
      expect(article.summary).not.toBe('')
      expect(article.content.length).toBeGreaterThan(0)
      expect(CAM_NANG_CATEGORIES.map((category) => category.id)).toContain(article.category)
    }
  })
})

describe('cam-nang index route', () => {
  it('lists the seeded articles grouped under their category headings', () => {
    const { container } = render(<CamNangIndexPage />)

    // Every seeded article is linked to its detail route.
    for (const slug of SEEDED_SLUGS) {
      expect(container.querySelector(`a[href="/cam-nang/${slug}"]`)).not.toBeNull()
    }
    // Each non-empty category renders its Vietnamese heading.
    for (const { label } of CAM_NANG_CATEGORIES) {
      expect(container.textContent).toContain(label)
    }
  })
})

describe('cam-nang article rendering', () => {
  it('renders an article markdown body (headings, tables, bold)', () => {
    const article = getArticleBySlug('kien-thuc-ve-gas-lpg')
    expect(article).toBeDefined()

    const { container } = render(<MarkdownContent content={article!.content} />)

    // GFM table + markdown emphasis/headings are converted to real elements,
    // not left as literal markdown syntax.
    expect(container.querySelector('h2')).not.toBeNull()
    expect(container.querySelector('table')).not.toBeNull()
    expect(container.querySelector('strong')).not.toBeNull()
    expect(container.textContent).toContain('LPG')
    expect(container.textContent).not.toContain('##')
  })
})
