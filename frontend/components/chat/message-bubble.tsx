import { Bot, UserRound } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { cn } from '@/lib/utils'
import type { Message } from '@/types/conversation'
import { FeedbackButtons } from './feedback-buttons'

type MessageBubbleProps = {
  conversationId: string
  message: Message
}

export function MessageBubble({ conversationId, message }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const isStaff = message.role === 'staff'
  const shouldRenderMarkdown = message.role === 'assistant'

  return (
    <div className={cn('flex gap-2', isUser && 'flex-row-reverse')}>
      <Avatar className="h-8 w-8">
        <AvatarFallback
          className={cn(isUser ? 'bg-slate-900 text-white' : 'bg-sky-100 text-sky-800')}
        >
          {isUser ? <UserRound className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
        </AvatarFallback>
      </Avatar>
      <div className={cn('max-w-[78%]', isUser && 'items-end text-right')}>
        <div
          className={cn(
            'rounded-lg px-3 py-2 text-sm leading-6',
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
        <FeedbackButtons conversationId={conversationId} message={message} />
      </div>
    </div>
  )
}
