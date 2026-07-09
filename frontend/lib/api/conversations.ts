import { apiClient } from '@/lib/api/client'
import type {
  Conversation,
  ConversationListResponse,
  FeedbackRequest,
  Message,
  MessageListResponse,
  ResolveRequest,
  SendMessageRequest,
  SendMessageResponse,
  SettableConversationStatus,
  StaffMessageRequest,
  StartConversationRequest,
  TransferRequest,
} from '@/types/conversation'

export async function startConversation(data: StartConversationRequest): Promise<Conversation> {
  const response = await apiClient.post<Conversation>('/api/v1/conversations/start', data)
  return response.data
}

export async function getActiveConversation(sessionId: string): Promise<Conversation | null> {
  const response = await apiClient.get<Conversation | null>('/api/v1/conversations/active', {
    params: { session_id: sessionId },
  })
  return response.data
}

export async function getConversation(conversationId: string): Promise<Conversation> {
  const response = await apiClient.get<Conversation>(`/api/v1/conversations/${conversationId}`)
  return response.data
}

export async function listMessages(conversationId: string): Promise<MessageListResponse> {
  const response = await apiClient.get<MessageListResponse>(
    `/api/v1/conversations/${conversationId}/messages`
  )
  return response.data
}

export async function sendMessage(
  conversationId: string,
  data: SendMessageRequest
): Promise<SendMessageResponse> {
  const response = await apiClient.post<SendMessageResponse>(
    `/api/v1/conversations/${conversationId}/messages`,
    data
  )
  return response.data
}

export async function submitFeedback(
  conversationId: string,
  messageId: string,
  data: FeedbackRequest
): Promise<Message> {
  const response = await apiClient.post<Message>(
    `/api/v1/conversations/${conversationId}/messages/${messageId}/feedback`,
    data
  )
  return response.data
}

export async function resolveConversation(
  conversationId: string,
  data: ResolveRequest = {}
): Promise<Conversation> {
  const response = await apiClient.post<Conversation>(
    `/api/v1/conversations/${conversationId}/resolve`,
    data
  )
  return response.data
}

export async function updateConversationStatus(
  conversationId: string,
  status: SettableConversationStatus
): Promise<Conversation> {
  const response = await apiClient.patch<Conversation>(
    `/api/v1/staff/conversations/${conversationId}/status`,
    { status }
  )
  return response.data
}

export async function listStaffConversations(params: {
  status?: string
  skip?: number
  limit?: number
}): Promise<ConversationListResponse> {
  const response = await apiClient.get<ConversationListResponse>(
    '/api/v1/staff/conversations/assigned',
    { params }
  )
  return response.data
}

export async function sendStaffMessage(
  conversationId: string,
  data: StaffMessageRequest
): Promise<Message> {
  const response = await apiClient.post<Message>(
    `/api/v1/staff/conversations/${conversationId}/messages`,
    data
  )
  return response.data
}

export async function transferConversation(
  conversationId: string,
  data: TransferRequest
): Promise<Conversation> {
  const response = await apiClient.post<Conversation>(
    `/api/v1/staff/conversations/${conversationId}/transfer`,
    data
  )
  return response.data
}
