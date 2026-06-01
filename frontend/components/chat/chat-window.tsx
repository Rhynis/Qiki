'use client'

import { MessageCircle, Minus, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { useMessages, useSendMessage, useStartConversation } from '@/lib/hooks/use-conversation'
import { useChatStore } from '@/lib/stores/chat-store'
import { EscalationNotice } from './escalation-notice'
import { MessageInput } from './message-input'
import { MessageList } from './message-list'

const MESSAGE_RATE_LIMIT_COUNT = 10
const MESSAGE_RATE_LIMIT_WINDOW_MS = 60_000

export function ChatWindow() {
  const close = useChatStore((state) => state.close)
  const sessionId = useChatStore((state) => state.sessionId)
  const conversationId = useChatStore((state) => state.conversationId)
  const setConversationId = useChatStore((state) => state.setConversationId)
  const sentAtRef = useRef<number[]>([])
  const rateLimitTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [rateLimited, setRateLimited] = useState(false)
  const startConversation = useStartConversation()
  const sendMessage = useSendMessage()
  const messages = useMessages(conversationId, true, sendMessage.isPending)

  function clearRateLimitTimer() {
    if (rateLimitTimeoutRef.current) {
      clearTimeout(rateLimitTimeoutRef.current)
      rateLimitTimeoutRef.current = null
    }
  }

  function scheduleRateLimitReset(recentSentAt: number[], now: number) {
    clearRateLimitTimer()
    const oldestTimestamp = recentSentAt[0]
    if (oldestTimestamp === undefined) return

    const waitMs = Math.max(MESSAGE_RATE_LIMIT_WINDOW_MS - (now - oldestTimestamp) + 100, 100)
    rateLimitTimeoutRef.current = setTimeout(() => {
      const nextNow = Date.now()
      const nextSentAt = sentAtRef.current.filter(
        (timestamp) => nextNow - timestamp < MESSAGE_RATE_LIMIT_WINDOW_MS
      )
      sentAtRef.current = nextSentAt
      const stillLimited = nextSentAt.length >= MESSAGE_RATE_LIMIT_COUNT
      setRateLimited(stillLimited)
      if (stillLimited) scheduleRateLimitReset(nextSentAt, nextNow)
    }, waitMs)
  }

  useEffect(() => {
    if (!conversationId && !startConversation.isPending) {
      startConversation.mutate({ session_id: sessionId })
    }
  }, [conversationId, sessionId, startConversation])

  useEffect(() => {
    if (startConversation.data?.id) setConversationId(startConversation.data.id)
  }, [setConversationId, startConversation.data?.id])

  useEffect(
    () => () => {
      if (rateLimitTimeoutRef.current) clearTimeout(rateLimitTimeoutRef.current)
    },
    []
  )

  const latestConversation = startConversation.data
  const isEscalated = latestConversation?.status === 'escalated'
  const isBusy = sendMessage.isPending || startConversation.isPending
  const conversationReady = Boolean(conversationId ?? startConversation.data?.id)

  function handleSend(content: string) {
    const targetConversationId = conversationId ?? startConversation.data?.id
    if (!targetConversationId) return false

    const now = Date.now()
    const recentSentAt = sentAtRef.current.filter(
      (timestamp) => now - timestamp < MESSAGE_RATE_LIMIT_WINDOW_MS
    )
    sentAtRef.current = recentSentAt
    if (recentSentAt.length >= MESSAGE_RATE_LIMIT_COUNT) {
      setRateLimited(true)
      scheduleRateLimitReset(recentSentAt, now)
      return false
    }

    sentAtRef.current = [...recentSentAt, now]
    setRateLimited(false)
    sendMessage.mutate({
      conversationId: targetConversationId,
      data: { content, session_id: sessionId },
    })
    return true
  }

  return (
    <section className="fixed bottom-24 right-4 z-50 w-[calc(100vw-2rem)] max-w-md overflow-hidden rounded-lg border bg-slate-50 shadow-xl md:right-6">
      <header className="flex items-center justify-between border-b bg-slate-900 px-4 py-3 text-white">
        <div className="flex items-center gap-2">
          <MessageCircle className="h-5 w-5" />
          <div>
            <p className="text-sm font-semibold">Qiki</p>
            <p className="text-xs text-slate-300">Trợ lý Gas Quốc Cường</p>
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
        rateLimited={rateLimited}
        sending={sendMessage.isPending}
        onSend={handleSend}
      />
    </section>
  )
}
