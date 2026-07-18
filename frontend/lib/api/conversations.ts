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

export type StreamMessageHandlers = {
  onDelta: (text: string) => void
  onDone: (response: SendMessageResponse) => void
}

type SseFrame = { event: string; data: string }

/** Split a raw SSE chunk buffer into complete frames, returning the leftover. */
export function parseSseFrames(buffer: string): { frames: SseFrame[]; rest: string } {
  const frames: SseFrame[] = []
  let rest = buffer
  let separator = rest.indexOf('\n\n')
  while (separator !== -1) {
    const raw = rest.slice(0, separator)
    rest = rest.slice(separator + 2)
    let event = 'message'
    const dataLines: string[] = []
    for (const line of raw.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
    }
    if (dataLines.length > 0) frames.push({ event, data: dataLines.join('\n') })
    separator = rest.indexOf('\n\n')
  }
  return { frames, rest }
}

/**
 * Stream a customer message as Server-Sent Events: `onDelta` fires per token and
 * `onDone` fires once with the persisted turn. Throws on a non-OK/unsupported
 * response so the caller can fall back to the blocking endpoint.
 */
export async function streamMessage(
  conversationId: string,
  data: SendMessageRequest,
  handlers: StreamMessageHandlers,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(`/api/v1/conversations/${conversationId}/messages/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
    signal,
  })
  if (!response.ok || !response.body) {
    throw new Error(`Streaming request failed with status ${response.status}`)
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let receivedDone = false
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const { frames, rest } = parseSseFrames(buffer)
    buffer = rest
    for (const frame of frames) {
      if (frame.event === 'delta') {
        handlers.onDelta((JSON.parse(frame.data) as { text: string }).text)
      } else if (frame.event === 'done') {
        receivedDone = true
        handlers.onDone(JSON.parse(frame.data) as SendMessageResponse)
      }
    }
  }
  // A stream that ends without a terminal `done` frame is treated as a failure so
  // the caller can fall back to the blocking endpoint (e.g. an SSE-unaware proxy).
  if (!receivedDone) {
    throw new Error('Stream ended before the final event')
  }
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
