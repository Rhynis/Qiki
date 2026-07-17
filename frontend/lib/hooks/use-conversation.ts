'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useState } from 'react'
import { toast } from 'sonner'
import * as conversationsApi from '@/lib/api/conversations'
import { useChatStore } from '@/lib/stores/chat-store'
import type {
  Conversation,
  FeedbackRequest,
  Message,
  MessageListResponse,
  ResolveRequest,
  SendMessageRequest,
  SettableConversationStatus,
  StaffMessageRequest,
  StartConversationRequest,
  TransferRequest,
} from '@/types/conversation'

export const conversationKeys = {
  all: ['conversations'] as const,
  active: (sessionId: string) => [...conversationKeys.all, 'active', sessionId] as const,
  detail: (conversationId: string) => [...conversationKeys.all, 'detail', conversationId] as const,
  messages: (conversationId: string) =>
    [...conversationKeys.all, 'messages', conversationId] as const,
  staffList: (params: Record<string, unknown>) =>
    [...conversationKeys.all, 'staff', params] as const,
  // Stable key so the in-flight send can be observed globally (via useIsMutating)
  // even after the chat window unmounts on close — the typing state then resumes.
  send: ['conversations', 'send'] as const,
}

const DEFAULT_MESSAGE_LIST: MessageListResponse = { items: [], total: 0, skip: 0, limit: 50 }

function messageTimestamp(message: Message) {
  const timestamp = Date.parse(message.created_at)
  return Number.isNaN(timestamp) ? 0 : timestamp
}

export function reconcileMessageList(
  incoming: MessageListResponse,
  previous?: MessageListResponse
): MessageListResponse {
  if (!previous) return incoming

  const previousById = new Map(previous.items.map((message) => [message.id, message]))
  const orderById = new Map<string, number>()

  previous.items.forEach((message, index) => {
    orderById.set(message.id, index)
  })
  incoming.items.forEach((message, index) => {
    if (!orderById.has(message.id)) orderById.set(message.id, previous.items.length + index)
  })

  const messagesById = new Map<string, Message>()
  incoming.items.forEach((message) => {
    const previousMessage = previousById.get(message.id)
    const products = previousMessage?.products?.length ? previousMessage.products : message.products
    messagesById.set(message.id, products ? { ...message, products } : message)
  })
  previous.items.forEach((message) => {
    if (!messagesById.has(message.id)) messagesById.set(message.id, message)
  })

  const items = Array.from(messagesById.values()).sort((left, right) => {
    const timestampDiff = messageTimestamp(left) - messageTimestamp(right)
    if (timestampDiff !== 0) return timestampDiff
    return (orderById.get(left.id) ?? 0) - (orderById.get(right.id) ?? 0)
  })

  return {
    ...incoming,
    items,
    total: Math.max(incoming.total, items.length),
  }
}

export function useStartConversation() {
  const queryClient = useQueryClient()
  const setConversationId = useChatStore((state) => state.setConversationId)

  return useMutation({
    mutationFn: (data: StartConversationRequest) => conversationsApi.startConversation(data),
    onSuccess: async (conversation) => {
      setConversationId(conversation.id)
      queryClient.setQueryData(conversationKeys.detail(conversation.id), conversation)
      await queryClient.invalidateQueries({ queryKey: conversationKeys.all })
    },
  })
}

export function useActiveConversation(sessionId: string, enabled = true) {
  return useQuery({
    queryKey: conversationKeys.active(sessionId),
    queryFn: () => conversationsApi.getActiveConversation(sessionId),
    enabled,
  })
}

export function useConversation(conversationId?: string) {
  return useQuery({
    queryKey: conversationKeys.detail(conversationId ?? ''),
    queryFn: () => conversationsApi.getConversation(conversationId ?? ''),
    enabled: Boolean(conversationId),
  })
}

export function useMessages(conversationId?: string, enabled = true, paused = false) {
  const queryClient = useQueryClient()
  const isOpen = useChatStore((state) => state.isOpen)
  const queryKey = conversationKeys.messages(conversationId ?? '')

  return useQuery({
    queryKey,
    queryFn: async () => {
      const incoming = await conversationsApi.listMessages(conversationId ?? '')
      const previous = queryClient.getQueryData<MessageListResponse>(queryKey)
      return reconcileMessageList(incoming, previous)
    },
    enabled: Boolean(conversationId) && enabled,
    // Pause polling while a send is in flight so a refetch doesn't clobber the
    // optimistic user message (the server hasn't committed it until the reply).
    refetchInterval: isOpen && conversationId && !paused ? 3000 : false,
  })
}

export function useSendMessage() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationKey: conversationKeys.send,
    mutationFn: ({ conversationId, data }: { conversationId: string; data: SendMessageRequest }) =>
      conversationsApi.sendMessage(conversationId, data),
    onMutate: async ({ conversationId, data }) => {
      const key = conversationKeys.messages(conversationId)
      await queryClient.cancelQueries({ queryKey: key })
      const previous = queryClient.getQueryData<MessageListResponse>(key)
      const optimisticMessage: Message = {
        id: `optimistic-${Date.now()}`,
        conversation_id: conversationId,
        role: 'user',
        content: data.content,
        flagged_for_review: false,
        is_emergency: false,
        created_at: new Date().toISOString(),
      }
      queryClient.setQueryData<MessageListResponse>(key, (old) => {
        const base = old ?? DEFAULT_MESSAGE_LIST
        return { ...base, items: [...base.items, optimisticMessage], total: base.total + 1 }
      })
      return { previous, conversationId }
    },
    onError: (_error, _variables, context) => {
      if (context?.previous !== undefined) {
        queryClient.setQueryData(
          conversationKeys.messages(context.conversationId),
          context.previous
        )
      }
      toast.error('Không gửi được tin nhắn. Vui lòng thử lại.')
    },
    onSuccess: (response) => {
      queryClient.setQueryData(
        conversationKeys.detail(response.conversation.id),
        response.conversation
      )
      const assistantMessage = response.assistant_message
        ? { ...response.assistant_message, products: response.products }
        : null
      queryClient.setQueryData<MessageListResponse>(
        conversationKeys.messages(response.conversation.id),
        (old) => {
          const base = old ?? DEFAULT_MESSAGE_LIST
          const items = base.items.filter(
            (message) =>
              !message.id.startsWith('optimistic-') &&
              message.id !== response.user_message.id &&
              message.id !== assistantMessage?.id
          )
          const incomingItems = [
            response.user_message,
            ...(assistantMessage ? [assistantMessage] : []),
          ]
          return reconcileMessageList(
            {
              ...base,
              items: incomingItems,
              total: incomingItems.length,
            },
            { ...base, items }
          )
        }
      )
      if (response.assistant_message?.is_emergency) {
        toast.error('Khẩn cấp an toàn gas: gọi 114 hoặc 115 ngay', {
          className: 'w-auto max-w-[calc(100vw-2rem)] whitespace-nowrap',
        })
      }
    },
    onSettled: async (_data, _error, variables) => {
      await queryClient.invalidateQueries({
        queryKey: conversationKeys.messages(variables.conversationId),
      })
    },
  })
}

/**
 * Streaming counterpart of useSendMessage: shows the user message optimistically,
 * then appends assistant tokens to a growing bubble as they arrive. Rejects on a
 * transport/parse error (after rolling back) so the caller can fall back to the
 * blocking endpoint.
 */
export function useStreamMessage() {
  const queryClient = useQueryClient()
  const [isStreaming, setIsStreaming] = useState(false)

  const streamSend = useCallback(
    async ({ conversationId, data }: { conversationId: string; data: SendMessageRequest }) => {
      const key = conversationKeys.messages(conversationId)
      await queryClient.cancelQueries({ queryKey: key })
      const previous = queryClient.getQueryData<MessageListResponse>(key)
      const now = new Date().toISOString()
      const userId = `optimistic-${Date.now()}`
      const assistantId = `streaming-${Date.now()}`
      queryClient.setQueryData<MessageListResponse>(key, (old) => {
        const base = old ?? DEFAULT_MESSAGE_LIST
        const userMessage: Message = {
          id: userId,
          conversation_id: conversationId,
          role: 'user',
          content: data.content,
          flagged_for_review: false,
          is_emergency: false,
          created_at: now,
        }
        return { ...base, items: [...base.items, userMessage], total: base.total + 1 }
      })
      setIsStreaming(true)
      let started = false
      const appendDelta = (text: string) => {
        queryClient.setQueryData<MessageListResponse>(key, (old) => {
          const base = old ?? DEFAULT_MESSAGE_LIST
          if (!started) {
            started = true
            const assistantMessage: Message = {
              id: assistantId,
              conversation_id: conversationId,
              role: 'assistant',
              content: text,
              flagged_for_review: false,
              is_emergency: false,
              created_at: new Date().toISOString(),
            }
            return { ...base, items: [...base.items, assistantMessage], total: base.total + 1 }
          }
          return {
            ...base,
            items: base.items.map((message) =>
              message.id === assistantId ? { ...message, content: message.content + text } : message
            ),
          }
        })
      }
      try {
        await conversationsApi.streamMessage(conversationId, data, {
          onDelta: appendDelta,
          onDone: (response) => {
            queryClient.setQueryData(
              conversationKeys.detail(response.conversation.id),
              response.conversation
            )
            const finalAssistant = response.assistant_message
              ? { ...response.assistant_message, products: response.products }
              : null
            queryClient.setQueryData<MessageListResponse>(key, (old) => {
              const base = old ?? DEFAULT_MESSAGE_LIST
              const items = base.items.filter(
                (message) =>
                  message.id !== userId &&
                  message.id !== assistantId &&
                  !message.id.startsWith('optimistic-')
              )
              const incoming = [response.user_message, ...(finalAssistant ? [finalAssistant] : [])]
              return reconcileMessageList(
                { ...base, items: incoming, total: incoming.length },
                { ...base, items }
              )
            })
            if (response.assistant_message?.is_emergency) {
              toast.error('Khẩn cấp an toàn gas: gọi 114 hoặc 115 ngay', {
                className: 'w-auto max-w-[calc(100vw-2rem)] whitespace-nowrap',
              })
            }
          },
        })
      } catch (error) {
        // Roll back so the caller can retry through the blocking endpoint.
        queryClient.setQueryData(key, previous)
        throw error
      } finally {
        setIsStreaming(false)
        await queryClient.invalidateQueries({ queryKey: key })
      }
    },
    [queryClient]
  )

  return { streamSend, isStreaming }
}

export function useSubmitFeedback() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      conversationId,
      messageId,
      data,
    }: {
      conversationId: string
      messageId: string
      data: FeedbackRequest
    }) => conversationsApi.submitFeedback(conversationId, messageId, data),
    onMutate: async ({ conversationId, messageId, data }) => {
      const messagesKey = conversationKeys.messages(conversationId)
      const detailKey = conversationKeys.detail(conversationId)
      await queryClient.cancelQueries({ queryKey: messagesKey })
      await queryClient.cancelQueries({ queryKey: detailKey })

      const previousMessages = queryClient.getQueryData<MessageListResponse>(messagesKey)
      const previousConversation = queryClient.getQueryData<Conversation>(detailKey)
      const applyFeedback = (message: Message): Message =>
        message.id === messageId ? { ...message, feedback_score: data.score } : message

      queryClient.setQueryData<MessageListResponse>(messagesKey, (old) =>
        old ? { ...old, items: old.items.map(applyFeedback) } : old
      )
      queryClient.setQueryData<Conversation>(detailKey, (old) =>
        old ? { ...old, messages: old.messages.map(applyFeedback) } : old
      )

      return { conversationId, previousConversation, previousMessages }
    },
    onError: (_error, _variables, context) => {
      if (context?.previousMessages !== undefined) {
        queryClient.setQueryData(
          conversationKeys.messages(context.conversationId),
          context.previousMessages
        )
      }
      if (context?.previousConversation !== undefined) {
        queryClient.setQueryData(
          conversationKeys.detail(context.conversationId),
          context.previousConversation
        )
      }
      toast.error('Không gửi được phản hồi. Vui lòng thử lại.')
    },
    onSettled: async (_message, _error, variables) => {
      await queryClient.invalidateQueries({
        queryKey: conversationKeys.messages(variables.conversationId),
      })
    },
  })
}

export function useStaffConversations(params: { status?: string; skip?: number; limit?: number }) {
  return useQuery({
    queryKey: conversationKeys.staffList(params),
    queryFn: () => conversationsApi.listStaffConversations(params),
    refetchInterval: 3000,
  })
}

export function useSendStaffMessage() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ conversationId, data }: { conversationId: string; data: StaffMessageRequest }) =>
      conversationsApi.sendStaffMessage(conversationId, data),
    onSuccess: async (_message, variables) => {
      await queryClient.invalidateQueries({
        queryKey: conversationKeys.messages(variables.conversationId),
      })
      await queryClient.invalidateQueries({ queryKey: conversationKeys.all })
    },
  })
}

export function useTransferConversation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ conversationId, data }: { conversationId: string; data: TransferRequest }) =>
      conversationsApi.transferConversation(conversationId, data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: conversationKeys.all })
    },
  })
}

export function useResolveConversation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ conversationId, data }: { conversationId: string; data?: ResolveRequest }) =>
      conversationsApi.resolveConversation(conversationId, data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: conversationKeys.all })
      toast.success('Đã kết thúc cuộc trò chuyện')
    },
  })
}

export function useUpdateConversationStatus() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      conversationId,
      status,
    }: {
      conversationId: string
      status: SettableConversationStatus
    }) => conversationsApi.updateConversationStatus(conversationId, status),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: conversationKeys.all })
      toast.success('Đã cập nhật trạng thái')
    },
  })
}
