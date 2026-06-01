'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
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
  const isOpen = useChatStore((state) => state.isOpen)

  return useQuery({
    queryKey: conversationKeys.messages(conversationId ?? ''),
    queryFn: () => conversationsApi.listMessages(conversationId ?? ''),
    enabled: Boolean(conversationId) && enabled,
    // Pause polling while a send is in flight so a refetch doesn't clobber the
    // optimistic user message (the server hasn't committed it until the reply).
    refetchInterval: isOpen && conversationId && !paused ? 3000 : false,
  })
}

export function useSendMessage() {
  const queryClient = useQueryClient()

  return useMutation({
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
        const base = old ?? { items: [], total: 0, skip: 0, limit: 50 }
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
      if (response.assistant_message?.is_emergency) {
        toast.error('Khẩn cấp an toàn gas: gọi 114 hoặc 115 ngay')
      }
    },
    onSettled: async (_data, _error, variables) => {
      await queryClient.invalidateQueries({
        queryKey: conversationKeys.messages(variables.conversationId),
      })
    },
  })
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
