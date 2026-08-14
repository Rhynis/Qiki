'use client'

import { useCallback, useState } from 'react'
import { v4 as uuidv4 } from 'uuid'
import { streamAgentTurn } from '@/lib/api/agent'
import { useChatStore } from '@/lib/stores/chat-store'
import type { Message } from '@/types/conversation'

/**
 * Minimal local-state counterpart of useConversation/useStreamMessage for the
 * LangGraph agent path (AGENT_ENABLED). Not backed by react-query: the agent
 * MVP has no persisted Conversation/Message DB rows to fetch/reconcile — the
 * LangGraph Postgres checkpointer is the durable store (ADR-0002), keyed by
 * the SAME session_id the RAG chat already tracks in useChatStore, so the
 * transcript shown here is just this tab's client-side view of that thread.
 */
export function useAgentChat() {
  const sessionId = useChatStore((state) => state.sessionId)
  const markActivity = useChatStore((state) => state.markActivity)
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)

  const sendMessage = useCallback(
    (content: string) => {
      markActivity()
      const userMessage: Message = {
        id: uuidv4(),
        conversation_id: sessionId,
        role: 'user',
        content,
        flagged_for_review: false,
        is_emergency: false,
        created_at: new Date().toISOString(),
      }
      const assistantId = uuidv4()
      let started = false
      setMessages((previous) => [...previous, userMessage])
      setIsStreaming(true)

      void streamAgentTurn(
        { content, session_id: sessionId },
        {
          onToken: (text) => {
            setMessages((previous) => {
              if (!started) {
                started = true
                const assistantMessage: Message = {
                  id: assistantId,
                  conversation_id: sessionId,
                  role: 'assistant',
                  content: text,
                  flagged_for_review: false,
                  is_emergency: false,
                  created_at: new Date().toISOString(),
                }
                return [...previous, assistantMessage]
              }
              return previous.map((message) =>
                message.id === assistantId
                  ? { ...message, content: message.content + text }
                  : message
              )
            })
          },
          onDone: (event) => {
            // A short, non-streamed reply (e.g. the safety short-circuit) never
            // fires onToken — fall back to the done event's full content.
            if (!started) {
              const assistantMessage: Message = {
                id: assistantId,
                conversation_id: sessionId,
                role: 'assistant',
                content: event.content,
                llm_provider: event.llm_provider,
                flagged_for_review: false,
                is_emergency: false,
                created_at: new Date().toISOString(),
              }
              setMessages((previous) => [...previous, assistantMessage])
            }
          },
        }
      )
        .catch(() => {
          setMessages((previous) => previous.filter((message) => message.id !== userMessage.id))
        })
        .finally(() => setIsStreaming(false))

      return true
    },
    [markActivity, sessionId]
  )

  return { messages, sendMessage, isStreaming, sessionId }
}
