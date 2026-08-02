'use client'

import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

type MarkdownContentProps = {
  content: string
}

/**
 * Typographic renderer for the Cẩm nang article bodies. Uses react-markdown with
 * GFM (tables, strikethrough, autolinks) and no raw-HTML plugin, so the markdown
 * is rendered safely without HTML injection. Styling is done with brand tokens
 * via element overrides; wide content (tables/code) scrolls inside its own
 * horizontal-overflow container so the page body never scrolls sideways.
 */
export function MarkdownContent({ content }: MarkdownContentProps) {
  return (
    <div className="text-[15px] leading-7 text-slate-700">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h2: ({ children }) => (
            <h2 className="mt-8 scroll-mt-24 text-2xl font-semibold text-slate-950 first:mt-0">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="mt-6 text-xl font-semibold text-slate-950">{children}</h3>
          ),
          h4: ({ children }) => (
            <h4 className="mt-5 text-lg font-semibold text-slate-950">{children}</h4>
          ),
          p: ({ children }) => <p className="mt-4 first:mt-0">{children}</p>,
          ul: ({ children }) => (
            <ul className="mt-4 list-disc space-y-2 pl-6 marker:text-primary">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="mt-4 list-decimal space-y-2 pl-6 marker:text-primary">{children}</ol>
          ),
          li: ({ children }) => <li className="pl-1 leading-7">{children}</li>,
          strong: ({ children }) => (
            <strong className="font-semibold text-slate-950">{children}</strong>
          ),
          em: ({ children }) => <em className="italic">{children}</em>,
          a: ({ children, href }) => (
            <a
              href={href}
              className="font-medium text-primary underline underline-offset-2 hover:text-primary/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              target={href?.startsWith('http') ? '_blank' : undefined}
              rel={href?.startsWith('http') ? 'noreferrer' : undefined}
            >
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="mt-4 border-l-4 border-primary/30 bg-primary/5 py-1 pl-4 text-slate-700">
              {children}
            </blockquote>
          ),
          hr: () => <hr className="my-8 border-slate-200" />,
          table: ({ children }) => (
            <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full border-collapse text-left text-sm">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-slate-50">{children}</thead>,
          th: ({ children }) => (
            <th className="border-b border-slate-200 px-3 py-2 font-semibold text-slate-950">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border-b border-slate-100 px-3 py-2 align-top">{children}</td>
          ),
          code: ({ children }) => (
            <code className="rounded bg-slate-100 px-1.5 py-0.5 text-sm text-slate-800">
              {children}
            </code>
          ),
          pre: ({ children }) => (
            <pre className="mt-4 overflow-x-auto rounded-lg bg-slate-900 p-4 text-sm text-slate-100">
              {children}
            </pre>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
