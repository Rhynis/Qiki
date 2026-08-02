import fs from 'node:fs'
import path from 'node:path'

/** The four content buckets the guide is grouped by, in display order. */
export type CamNangCategory = 'an-toan' | 'kien-thuc-gas' | 'thuong-hieu' | 'nuoc-uong'

export type CamNangArticle = {
  slug: string
  title: string
  category: CamNangCategory
  order: number
  summary: string
  /** The markdown body (frontmatter stripped). */
  content: string
}

export type CamNangGroup = {
  category: CamNangCategory
  label: string
  articles: CamNangArticle[]
}

/**
 * Category display order + Vietnamese headings for the index page. This is a
 * user-facing label set (Vietnamese only), kept out of the i18n bundle because
 * the guide is Vietnamese-first content, not a localized UI surface.
 */
export const CAM_NANG_CATEGORIES: { id: CamNangCategory; label: string }[] = [
  { id: 'an-toan', label: 'An toàn sử dụng gas' },
  { id: 'kien-thuc-gas', label: 'Kiến thức về gas' },
  { id: 'thuong-hieu', label: 'Thương hiệu gas' },
  { id: 'nuoc-uong', label: 'Nước uống đóng bình' },
]

const VALID_CATEGORIES = new Set<string>(CAM_NANG_CATEGORIES.map((category) => category.id))

const CONTENT_DIR = path.join(process.cwd(), 'content', 'cam-nang')

/** Strip one layer of matching surrounding quotes and unescape doubled quotes. */
function unquote(value: string): string {
  const trimmed = value.trim()
  if (trimmed.length >= 2 && trimmed.startsWith("'") && trimmed.endsWith("'")) {
    return trimmed.slice(1, -1).replace(/''/g, "'")
  }
  if (trimmed.length >= 2 && trimmed.startsWith('"') && trimmed.endsWith('"')) {
    return trimmed.slice(1, -1).replace(/\\"/g, '"')
  }
  return trimmed
}

/**
 * Parse the small, fixed frontmatter block (`--- ... ---`) at the top of a file.
 * The frontmatter contract is a handful of `key: value` lines with simple scalar
 * values, so a tiny parser keeps the dependency footprint at zero rather than
 * pulling in a YAML stack for content we fully control.
 */
function parseFrontmatter(raw: string): { data: Record<string, string>; body: string } {
  const normalized = raw.replace(/\r\n/g, '\n')
  const match = normalized.match(/^---\n([\s\S]*?)\n---\n?/)
  if (!match) {
    return { data: {}, body: normalized.trim() }
  }

  const data: Record<string, string> = {}
  for (const line of (match[1] ?? '').split('\n')) {
    if (!line.trim()) continue
    const separator = line.indexOf(':')
    if (separator === -1) continue
    const key = line.slice(0, separator).trim()
    if (key) data[key] = unquote(line.slice(separator + 1))
  }

  return { data, body: normalized.slice(match[0].length).trim() }
}

function toArticle(fileName: string): CamNangArticle | null {
  const raw = fs.readFileSync(path.join(CONTENT_DIR, fileName), 'utf8')
  const { data, body } = parseFrontmatter(raw)

  const slug = data.slug || fileName.replace(/\.md$/, '')
  const category = data.category
  if (!category || !VALID_CATEGORIES.has(category)) return null

  const order = Number.parseInt(data.order ?? '', 10)

  return {
    slug,
    title: data.title ?? slug,
    category: category as CamNangCategory,
    order: Number.isNaN(order) ? Number.MAX_SAFE_INTEGER : order,
    summary: data.summary ?? '',
    content: body,
  }
}

let cachedArticles: CamNangArticle[] | null = null

/**
 * Read every guide article from the content folder, sorted by category display
 * order then the per-article `order`. Results are memoized because the markdown
 * is bundled at build time and never changes at runtime.
 */
export function getAllArticles(): CamNangArticle[] {
  if (cachedArticles) return cachedArticles

  const categoryRank = new Map<string, number>(
    CAM_NANG_CATEGORIES.map((category, index) => [category.id, index])
  )

  const files = fs.existsSync(CONTENT_DIR)
    ? fs.readdirSync(CONTENT_DIR).filter((file) => file.endsWith('.md'))
    : []

  cachedArticles = files
    .map(toArticle)
    .filter((article): article is CamNangArticle => article !== null)
    .sort((a, b) => {
      const byCategory = (categoryRank.get(a.category) ?? 0) - (categoryRank.get(b.category) ?? 0)
      if (byCategory !== 0) return byCategory
      if (a.order !== b.order) return a.order - b.order
      return a.title.localeCompare(b.title, 'vi')
    })

  return cachedArticles
}

/** Group the articles by category in display order, dropping empty categories. */
export function getArticlesByCategory(): CamNangGroup[] {
  const articles = getAllArticles()
  return CAM_NANG_CATEGORIES.map(({ id, label }) => ({
    category: id,
    label,
    articles: articles.filter((article) => article.category === id),
  })).filter((group) => group.articles.length > 0)
}

export function getArticleBySlug(slug: string): CamNangArticle | undefined {
  return getAllArticles().find((article) => article.slug === slug)
}

export function getAllSlugs(): string[] {
  return getAllArticles().map((article) => article.slug)
}
