'use client'

import { useIsMutating, useQueryClient } from '@tanstack/react-query'
import { MessageCircle, MessageSquarePlus, Minus, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  conversationKeys,
  useMessages,
  useSendMessage,
  useStartConversation,
} from '@/lib/hooks/use-conversation'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
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
  const markActivity = useChatStore((state) => state.markActivity)
  const resetSession = useChatStore((state) => state.resetSession)
  const startIfStale = useChatStore((state) => state.startIfStale)
  const queryClient = useQueryClient()
  const sentAtRef = useRef<number[]>([])
  const startAttemptedRef = useRef(false)
  const rateLimitTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [rateLimited, setRateLimited] = useState(false)
  const startConversation = useStartConversation()
  const sendMessage = useSendMessage()
  // Track the send globally so the "typing" indicator survives the window being
  // closed and reopened while a reply is still in flight (the mutation outlives
  // this component because it lives on the shared QueryClient).
  const isSending = useIsMutating({ mutationKey: conversationKeys.send }) > 0
  const messages = useMessages(conversationId, true, isSending)

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

  const clearChatQueryState = useCallback(
    (previousConversationId?: string, previousSessionId?: string, nextSessionId?: string) => {
      if (previousConversationId) {
        queryClient.removeQueries({ queryKey: conversationKeys.messages(previousConversationId) })
        queryClient.removeQueries({ queryKey: conversationKeys.detail(previousConversationId) })
      }
      if (previousSessionId) {
        queryClient.removeQueries({ queryKey: conversationKeys.active(previousSessionId) })
      }
      if (nextSessionId) {
        void queryClient.invalidateQueries({
          queryKey: conversationKeys.active(nextSessionId),
        })
      }
    },
    [queryClient]
  )

  useEffect(() => {
    const previousConversationId = useChatStore.getState().conversationId
    const previousSessionId = useChatStore.getState().sessionId
    startIfStale()
    const nextSessionId = useChatStore.getState().sessionId
    if (nextSessionId !== previousSessionId) {
      startAttemptedRef.current = false
      startConversation.reset()
      sendMessage.reset()
      sentAtRef.current = []
      clearRateLimitTimer()
      clearChatQueryState(previousConversationId, previousSessionId, nextSessionId)
    }
  }, [clearChatQueryState, sendMessage, startConversation, startIfStale])

  useEffect(() => {
    if (!conversationId && !startAttemptedRef.current) {
      startAttemptedRef.current = true
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
  const startFailed = startConversation.isError && !conversationId
  const isBusy = isSending || (startConversation.isPending && !startFailed)
  const conversationReady = Boolean(conversationId)

  function handleRetryStart() {
    startAttemptedRef.current = false
    startConversation.reset()
  }

  function handleNewConversation() {
    const previousConversationId = conversationId
    const previousSessionId = sessionId
    resetSession()
    const nextSessionId = useChatStore.getState().sessionId
    startAttemptedRef.current = false
    sentAtRef.current = []
    setRateLimited(false)
    clearRateLimitTimer()
    startConversation.reset()
    sendMessage.reset()
    clearChatQueryState(previousConversationId, previousSessionId, nextSessionId)
  }

  function handleSend(content: string) {
    if (!conversationId) return false

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
    markActivity()
    sendMessage.mutate({
      conversationId,
      data: { content, session_id: sessionId },
    })
    return true
  }

  return (
    <section className="fixed bottom-24 right-4 z-50 w-[calc(100vw-2rem)] max-w-md origin-bottom-right overflow-hidden rounded-lg border bg-slate-50 shadow-xl duration-200 ease-out animate-in fade-in zoom-in-95 slide-in-from-bottom-4 md:right-6">
      <header className="flex items-center justify-between border-b bg-slate-900 px-4 py-3 text-white">
        <div className="flex items-center gap-2">
          <MessageCircle className="h-5 w-5" />
          <div>
            <p className="text-sm font-semibold">Qiki</p>
            <p className="text-xs text-slate-300">Trợ lý Gas Quốc Cường</p>
          </div>
        </div>
        <div className="flex gap-1">
          <Tooltip delayDuration={150}>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-11 w-11 text-primary hover:bg-primary/10 hover:text-primary focus-visible:ring-ring"
                title="Tạo cuộc trò chuyện mới"
                aria-label="Tạo cuộc trò chuyện mới"
                onClick={handleNewConversation}
              >
                <MessageSquarePlus className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Tạo cuộc trò chuyện mới</TooltipContent>
          </Tooltip>
          <Tooltip delayDuration={150}>
            <TooltipTrigger asChild>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-11 w-11 text-white hover:bg-slate-700"
                title="Thu nhỏ"
                aria-label="Thu nhỏ"
                onClick={close}
              >
                <Minus className="h-4 w-4" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Thu nhỏ</TooltipContent>
          </Tooltip>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-11 w-11 text-white hover:bg-slate-700"
            title="Đóng"
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
        messages={messages.data?.items ?? []}
        isPending={isBusy}
      />
      {startFailed ? (
        <div className="border-t bg-white px-4 py-3">
          <div className="rounded-md border border-primary/20 bg-primary/5 p-3">
            <p className="text-sm font-medium text-slate-950">
              Không kết nối được với Qiki, vui lòng thử lại.
            </p>
            <Button
              className="mt-3 bg-primary text-primary-foreground hover:bg-primary/90"
              size="sm"
              type="button"
              onClick={handleRetryStart}
            >
              Thử lại
            </Button>
          </div>
        </div>
      ) : null}
      <MessageInput
        key={sessionId}
        disabled={!conversationReady || startConversation.isPending || startFailed}
        rateLimited={rateLimited}
        sending={isSending}
        onSend={handleSend}
      />
    </section>
  )
}
