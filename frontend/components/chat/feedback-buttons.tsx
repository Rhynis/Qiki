'use client'

import { Copy, ThumbsDown, ThumbsUp } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { useSubmitFeedback } from '@/lib/hooks/use-conversation'
import { cn } from '@/lib/utils'
import type { Message } from '@/types/conversation'
import { toast } from 'sonner'

type FeedbackButtonsProps = {
  conversationId: string
  message: Message
}

export function FeedbackButtons({ conversationId, message }: FeedbackButtonsProps) {
  const t = useTranslations('chat')
  const mutation = useSubmitFeedback()
  const pendingScore =
    mutation.isPending && mutation.variables?.messageId === message.id
      ? mutation.variables.data.score
      : undefined
  const feedbackScore = pendingScore ?? message.feedback_score ?? 0
  const hasFeedback = feedbackScore === 1 || feedbackScore === -1
  const feedbackDisabled = hasFeedback || mutation.isPending

  const isAssistant = message.role === 'assistant'
  const isUser = message.role === 'user'
  if (!isAssistant && !isUser) return null

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(message.content)
      toast.success(t('copied'))
    } catch {
      toast.error(t('copyFailed'))
    }
  }

  const copyButton = (
    <Button
      type="button"
      variant="ghost"
      size="icon"
      className="h-7 w-7 text-slate-500 hover:text-slate-900"
      aria-label={t('copyAria')}
      onClick={handleCopy}
    >
      <Copy className="h-3.5 w-3.5" />
    </Button>
  )

  if (isUser) {
    return <div className="mt-1 flex justify-end gap-1">{copyButton}</div>
  }

  return (
    <div className="mt-2 flex gap-1">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className={cn(
          'h-7 w-7 text-slate-500',
          feedbackScore === 1 &&
            'bg-green-50 text-green-600 ring-1 ring-green-600/20 hover:bg-green-50 hover:text-green-600 disabled:opacity-100',
          hasFeedback && feedbackScore !== 1 && 'disabled:opacity-40'
        )}
        aria-label={t('helpful')}
        disabled={feedbackDisabled}
        onClick={() =>
          mutation.mutate({ conversationId, messageId: message.id, data: { score: 1 } })
        }
      >
        <ThumbsUp className="h-3.5 w-3.5" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className={cn(
          'h-7 w-7 text-slate-500',
          feedbackScore === -1 &&
            'bg-red-50 text-red-600 ring-1 ring-red-600/20 hover:bg-red-50 hover:text-red-600 disabled:opacity-100',
          hasFeedback && feedbackScore !== -1 && 'disabled:opacity-40'
        )}
        aria-label={t('notHelpful')}
        disabled={feedbackDisabled}
        onClick={() =>
          mutation.mutate({ conversationId, messageId: message.id, data: { score: -1 } })
        }
      >
        <ThumbsDown className="h-3.5 w-3.5" />
      </Button>
      {copyButton}
    </div>
  )
}
