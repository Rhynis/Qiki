'use client'

import { CheckCircle2, PhoneCall, SendHorizonal } from 'lucide-react'
import { FormEvent, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Textarea } from '@/components/ui/textarea'
import {
  useConversation,
  useMessages,
  useResolveConversation,
  useSendStaffMessage,
} from '@/lib/hooks/use-conversation'
import { cn } from '@/lib/utils'
import { conversationFollowupNote } from '@/lib/utils/conversation-summary'
import { EmergencyBanner } from '@/components/chat/emergency-banner'

type ChatDetailStaffProps = {
  conversationId: string
}

export function ChatDetailStaff({ conversationId }: ChatDetailStaffProps) {
  const [content, setContent] = useState('')
  const conversation = useConversation(conversationId)
  const messages = useMessages(conversationId, true)
  const sendStaffMessage = useSendStaffMessage()
  const resolveConversation = useResolveConversation()
  const hasEmergency = messages.data?.items.some((message) => message.is_emergency)
  const followup = conversation.data
    ? conversationFollowupNote({
        ...conversation.data,
        messages: messages.data?.items ?? conversation.data.messages,
      })
    : null

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmed = content.trim()
    if (!trimmed) return
    sendStaffMessage.mutate({ conversationId, data: { content: trimmed } })
    setContent('')
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Chi tiết chat</h1>
          <p className="text-sm text-slate-600">
            {conversation.data?.session_id ?? conversationId}
          </p>
        </div>
        <div className="flex gap-2">
          <Badge variant="outline">{conversation.data?.status ?? 'loading'}</Badge>
          <Button
            type="button"
            variant="outline"
            disabled={resolveConversation.isPending}
            onClick={() => resolveConversation.mutate({ conversationId, data: {} })}
          >
            <CheckCircle2 className="mr-2 h-4 w-4" />
            Kết thúc
          </Button>
        </div>
      </div>

      {hasEmergency ? <EmergencyBanner /> : null}

      {followup ? (
        <div className="flex items-center gap-2 rounded-lg border border-primary/30 bg-primary/10 p-3 text-sm font-medium text-primary">
          <PhoneCall className="h-4 w-4 shrink-0" />
          {followup.staffReminder}
        </div>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Tin nhắn</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <ScrollArea className="h-[520px]">
            <div className="space-y-3 p-4">
              {(messages.data?.items ?? conversation.data?.messages ?? []).map((message) => {
                const isCustomer = message.role === 'user'
                return (
                  <div
                    key={message.id}
                    className={cn('flex', isCustomer ? 'justify-start' : 'justify-end')}
                  >
                    <div
                      className={cn(
                        'max-w-[72%] rounded-lg px-3 py-2 text-sm leading-6',
                        isCustomer && 'bg-slate-100 text-slate-900',
                        message.role === 'assistant' &&
                          'bg-sky-50 text-sky-900 ring-1 ring-sky-200',
                        message.role === 'staff' && 'bg-slate-900 text-white'
                      )}
                    >
                      <p>{message.content}</p>
                      {message.flagged_for_review ? (
                        <p className="mt-1 text-xs font-semibold text-red-700">Cần xem lại</p>
                      ) : null}
                    </div>
                  </div>
                )
              })}
            </div>
          </ScrollArea>
          <form className="flex gap-2 border-t p-3" onSubmit={handleSubmit}>
            <Textarea
              value={content}
              onChange={(event) => setContent(event.target.value)}
              placeholder="Trả lời khách hàng..."
              className="min-h-10 resize-none"
              rows={1}
            />
            <Button
              type="submit"
              size="icon"
              disabled={sendStaffMessage.isPending || !content.trim()}
            >
              <SendHorizonal className="h-4 w-4" />
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
