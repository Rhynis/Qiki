'use client'

import { MessageCircle, Minus, X } from 'lucide-react'
import { useEffect } from 'react'
import { Button } from '@/components/ui/button'
import { useMessages, useSendMessage, useStartConversation } from '@/lib/hooks/use-conversation'
import { useChatStore } from '@/lib/stores/chat-store'
import { EscalationNotice } from './escalation-notice'
import { MessageInput } from './message-input'
import { MessageList } from './message-list'

export function ChatWindow() {
  const close = useChatStore((state) => state.close)
  const sessionId = useChatStore((state) => state.sessionId)
  const conversationId = useChatStore((state) => state.conversationId)
  const setConversationId = useChatStore((state) => state.setConversationId)
  const startConversation = useStartConversation()
  const sendMessage = useSendMessage()
  const messages = useMessages(conversationId, true, sendMessage.isPending)

  useEffect(() => {
    if (!conversationId && !startConversation.isPending) {
      startConversation.mutate({ session_id: sessionId })
    }
  }, [conversationId, sessionId, startConversation])

  useEffect(() => {
    if (startConversation.data?.id) setConversationId(startConversation.data.id)
  }, [setConversationId, startConversation.data?.id])

  const latestConversation = startConversation.data
  const isEscalated = latestConversation?.status === 'escalated'
  const isBusy = sendMessage.isPending || startConversation.isPending
  const conversationReady = Boolean(conversationId ?? startConversation.data?.id)

  function handleSend(content: string) {
    const targetConversationId = conversationId ?? startConversation.data?.id
    if (!targetConversationId) return
    sendMessage.mutate({
      conversationId: targetConversationId,
      data: { content, session_id: sessionId },
    })
  }

  return (
    <section className="fixed bottom-24 right-4 z-50 w-[calc(100vw-2rem)] max-w-md overflow-hidden rounded-lg border bg-slate-50 shadow-xl md:right-6">
      <header className="flex items-center justify-between border-b bg-slate-900 px-4 py-3 text-white">
        <div className="flex items-center gap-2">
          <MessageCircle className="h-5 w-5" />
          <div>
            <p className="text-sm font-semibold">GasBot</p>
            <p className="text-xs text-slate-300">Hỗ trợ gas an toàn</p>
          </div>
        </div>
        <div className="flex gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-white hover:bg-slate-700"
            aria-label="Thu gọn"
            onClick={close}
          >
            <Minus className="h-4 w-4" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-white hover:bg-slate-700"
            aria-label="Đóng chat"
            onClick={close}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </header>
      {isEscalated ? (
        <div className="p-3">
          <EscalationNotice reason={latestConversation?.escalation_reason} />
        </div>
      ) : null}
      <MessageList
        conversationId={conversationId ?? ''}
        messages={messages.data?.items ?? latestConversation?.messages ?? []}
        isPending={isBusy}
      />
      <MessageInput
        disabled={!conversationReady || startConversation.isPending}
        sending={sendMessage.isPending}
        onSend={handleSend}
      />
    </section>
  )
}
