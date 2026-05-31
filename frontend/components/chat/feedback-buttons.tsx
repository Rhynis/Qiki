'use client'

import { Copy, ThumbsDown, ThumbsUp } from 'lucide-react'
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
  const mutation = useSubmitFeedback()
  const pendingScore =
    mutation.isPending && mutation.variables?.messageId === message.id
      ? mutation.variables.data.score
      : undefined
  const feedbackScore = pendingScore ?? message.feedback_score ?? 0
  const hasFeedback = feedbackScore === 1 || feedbackScore === -1
  const feedbackDisabled = hasFeedback || mutation.isPending

  if (message.role !== 'assistant') return null

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(message.content)
      toast.success('Đã sao chép')
    } catch {
      toast.error('Không sao chép được')
    }
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
        aria-label="Hài lòng"
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
        aria-label="Chưa hài lòng"
        disabled={feedbackDisabled}
        onClick={() =>
          mutation.mutate({ conversationId, messageId: message.id, data: { score: -1 } })
        }
      >
        <ThumbsDown className="h-3.5 w-3.5" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        className="h-7 w-7 text-slate-500 hover:text-slate-900"
        aria-label="Sao chép câu trả lời"
        onClick={handleCopy}
      >
        <Copy className="h-3.5 w-3.5" />
      </Button>
    </div>
  )
}
