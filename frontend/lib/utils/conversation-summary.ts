/**
 * Derive human-readable summaries for admin chat conversation rows
 * (title, intent label, last activity, relative time, search matching).
 */
import { formatPhone } from '@/lib/utils/format'
import type { Conversation, Message } from '@/types/conversation'

export type ChatFilter = 'all' | 'escalated' | 'emergency' | 'flagged'

const VN_PHONE = /(?:^|[^\d])((?:\+84|0)\d{9})(?!\d)/
const SNIPPET_MAX = 60

const intentLabels: Record<string, string> = {
  place_order: 'Đặt hàng',
  product_inquiry: 'Hỏi sản phẩm',
  order_status: 'Tra cứu đơn',
  safety_emergency: 'Khẩn cấp an toàn',
  complaint: 'Khiếu nại',
  greeting: 'Chào hỏi',
  general_question: 'Hỏi chung',
  off_topic: 'Ngoài chủ đề',
}

/** Messages sorted oldest-first by created_at (stable for equal timestamps). */
export function sortedMessages(conversation: Conversation): Message[] {
  return [...conversation.messages].sort(
    (left, right) => Date.parse(left.created_at) - Date.parse(right.created_at)
  )
}

function firstUserMessage(conversation: Conversation): Message | undefined {
  return sortedMessages(conversation).find((message) => message.role === 'user')
}

function lastMessage(conversation: Conversation): Message | undefined {
  const messages = sortedMessages(conversation)
  return messages[messages.length - 1]
}

/** First Vietnamese phone number found in any message, normalised to 0xxxxxxxxx. */
export function conversationPhone(conversation: Conversation): string | null {
  for (const message of conversation.messages) {
    const match = VN_PHONE.exec(message.content)
    if (match?.[1]) return formatPhone(match[1])
  }
  return null
}

export function intentLabel(intent: string | null | undefined): string | null {
  if (!intent) return null
  return intentLabels[intent] ?? intent
}

export function conversationIntent(conversation: Conversation): string | null {
  return intentLabel(firstUserMessage(conversation)?.intent)
}

/** Title: phone if known, else a snippet of the first user message, else session id. */
export function conversationTitle(conversation: Conversation): string {
  const phone = conversationPhone(conversation)
  if (phone) return phone

  const firstUser = firstUserMessage(conversation)?.content.trim()
  if (firstUser) {
    return firstUser.length > SNIPPET_MAX ? `${firstUser.slice(0, SNIPPET_MAX)}…` : firstUser
  }

  return `Phiên ${conversation.session_id.slice(0, 8)}`
}

export function conversationLastText(conversation: Conversation): string {
  return lastMessage(conversation)?.content ?? 'Chưa có tin nhắn'
}

/** ISO timestamp of the most recent activity (last message, else updated_at). */
export function conversationLastActivity(conversation: Conversation): string {
  return lastMessage(conversation)?.created_at ?? conversation.updated_at
}

export function conversationHasEmergency(conversation: Conversation): boolean {
  return conversation.messages.some((message) => message.is_emergency)
}

export function conversationHasFlag(conversation: Conversation): boolean {
  return conversation.messages.some((message) => message.flagged_for_review)
}

export function matchesChatFilter(conversation: Conversation, filter: ChatFilter): boolean {
  switch (filter) {
    case 'escalated':
      return conversation.status === 'escalated'
    case 'emergency':
      return conversationHasEmergency(conversation)
    case 'flagged':
      return conversationHasFlag(conversation)
    default:
      return true
  }
}

/** Match against session id, detected phone, or any message text (case-insensitive). */
export function matchesConversationSearch(conversation: Conversation, query: string): boolean {
  const needle = query.trim().toLowerCase()
  if (!needle) return true
  if (conversation.session_id.toLowerCase().includes(needle)) return true
  const phone = conversationPhone(conversation)
  if (phone && phone.includes(needle)) return true
  return conversation.messages.some((message) => message.content.toLowerCase().includes(needle))
}

/** Vietnamese relative time; falls back to a short date for older items. */
export function relativeTime(iso: string, now: number = Date.now()): string {
  const timestamp = Date.parse(iso)
  if (Number.isNaN(timestamp)) return ''

  const diffSeconds = Math.max(0, Math.round((now - timestamp) / 1000))
  if (diffSeconds < 60) return 'Vừa xong'

  const diffMinutes = Math.floor(diffSeconds / 60)
  if (diffMinutes < 60) return `${diffMinutes} phút trước`

  const diffHours = Math.floor(diffMinutes / 60)
  if (diffHours < 24) return `${diffHours} giờ trước`

  const diffDays = Math.floor(diffHours / 24)
  if (diffDays < 7) return `${diffDays} ngày trước`

  return new Intl.DateTimeFormat('vi-VN', { day: '2-digit', month: '2-digit' }).format(timestamp)
}
