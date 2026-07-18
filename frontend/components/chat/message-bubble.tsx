'use client'

import Link from 'next/link'
import { Bot, PackageOpen, UserRound } from 'lucide-react'
import { useTranslations } from 'next-intl'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { formatPrice, formatProductSize } from '@/lib/utils/format'
import { cn } from '@/lib/utils'
import type { Message, ProductCard } from '@/types/conversation'
import { FeedbackButtons } from './feedback-buttons'

type MessageBubbleProps = {
  conversationId: string
  message: Message
}

export function MessageBubble({ conversationId, message }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const isStaff = message.role === 'staff'
  const shouldRenderMarkdown = message.role === 'assistant'
  const products = shouldRenderMarkdown ? (message.products ?? []) : []

  return (
    <div className={cn('flex gap-2', isUser && 'flex-row-reverse')}>
      <Avatar className="h-8 w-8">
        <AvatarFallback
          className={cn(isUser ? 'bg-slate-900 text-white' : 'bg-sky-100 text-sky-800')}
        >
          {isUser ? <UserRound className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
        </AvatarFallback>
      </Avatar>
      <div className="max-w-[78%]">
        <div
          className={cn(
            'rounded-lg px-3 py-2 text-sm leading-6',
            // Plain-text bubbles (user/staff): left-align the text and wrap long
            // words so multi-line messages read cleanly. Assistant markdown is
            // left untouched.
            !shouldRenderMarkdown && 'whitespace-pre-wrap break-words text-left',
            isUser && 'bg-slate-900 text-white',
            !isUser && !isStaff && 'bg-white text-slate-800 shadow-sm ring-1 ring-slate-200',
            isStaff && 'bg-sky-700 text-white'
          )}
        >
          {shouldRenderMarkdown ? (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                ul: ({ children }) => (
                  <ul className="my-2 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="my-2 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>
                ),
                li: ({ children }) => <li className="pl-1">{children}</li>,
                strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                a: ({ children, href }) => (
                  <a
                    href={href}
                    className="font-medium underline underline-offset-2"
                    target="_blank"
                    rel="noreferrer"
                  >
                    {children}
                  </a>
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
          ) : (
            message.content
          )}
        </div>
        {products.length > 0 ? <ProductCards products={products} /> : null}
        <FeedbackButtons conversationId={conversationId} message={message} />
      </div>
    </div>
  )
}

type ProductCardsProps = {
  products: ProductCard[]
}

function ProductCards({ products }: ProductCardsProps) {
  const t = useTranslations('chat')
  return (
    <div className="mt-2 grid gap-2 sm:grid-cols-2">
      {products.map((product) => (
        <article
          key={product.id}
          className="flex h-full flex-col overflow-hidden rounded-lg bg-white text-left shadow-sm ring-1 ring-slate-200"
        >
          <div className="flex aspect-[4/3] items-center justify-center bg-slate-100">
            {product.image_url ? (
              <div
                aria-label={product.name}
                className="h-full w-full bg-cover bg-center"
                style={{ backgroundImage: `url(${product.image_url})` }}
              />
            ) : (
              <PackageOpen className="h-8 w-8 text-slate-400" />
            )}
          </div>
          <div className="flex flex-1 flex-col gap-2 p-3">
            <div className="min-w-0">
              <p className="truncate text-xs text-slate-500">
                {product.brand} · {formatProductSize(product.size_kg, product.unit ?? 'kg')}
              </p>
              <h3 className="line-clamp-2 min-h-[2.5rem] text-sm font-semibold leading-5 text-slate-900">
                {product.name}
              </h3>
            </div>
            <div className="space-y-1">
              <p className="text-sm font-semibold text-slate-900">{formatPrice(product.price)}</p>
              <p className="text-xs text-slate-500">
                {product.stock_quantity > 0
                  ? t('stockLeft', { count: product.stock_quantity })
                  : t('outOfStock')}
              </p>
            </div>
            <Link
              href={`/products/${product.id}`}
              className="mt-auto block rounded-md bg-slate-900 px-3 py-2 text-center text-xs font-medium text-white transition hover:bg-slate-700"
            >
              {t('viewAndOrder')}
            </Link>
          </div>
        </article>
      ))}
    </div>
  )
}
