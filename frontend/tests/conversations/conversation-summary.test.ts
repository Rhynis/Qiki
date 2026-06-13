import { describe, expect, it } from 'vitest'
import {
  conversationFollowupNote,
  conversationIntent,
  conversationLastActivity,
  conversationPhone,
  conversationTitle,
  matchesChatFilter,
  matchesConversationSearch,
  relativeTime,
} from '@/lib/utils/conversation-summary'
import type { Conversation, ConversationStatus, Message } from '@/types/conversation'

function message(overrides: Partial<Message> = {}): Message {
  return {
    id: overrides.id ?? Math.random().toString(36).slice(2),
    conversation_id: 'c1',
    role: 'user',
    content: '',
    flagged_for_review: false,
    is_emergency: false,
    created_at: '2026-06-13T10:00:00.000Z',
    ...overrides,
  }
}

function conversation(messages: Message[], status: ConversationStatus = 'active'): Conversation {
  return {
    id: 'c1',
    session_id: 'verify-12008-abcdef',
    status,
    messages,
    created_at: '2026-06-13T10:00:00.000Z',
    updated_at: '2026-06-13T10:05:00.000Z',
  }
}

describe('conversation summary', () => {
  it('uses a detected phone number as the title', () => {
    const convo = conversation([
      message({ role: 'user', content: 'Mình cần đặt gas, sđt 0903026306 nhé' }),
    ])
    expect(conversationPhone(convo)).toBe('0903026306')
    expect(conversationTitle(convo)).toBe('0903026306')
  })

  it('falls back to the first user message snippet', () => {
    const convo = conversation([
      message({ role: 'assistant', content: 'Xin chào, Qiki hỗ trợ gì ạ?' }),
      message({ role: 'user', content: 'Giá bình gas 12kg bao nhiêu?' }),
    ])
    expect(conversationTitle(convo)).toBe('Giá bình gas 12kg bao nhiêu?')
  })

  it('falls back to the session id when there is no user message', () => {
    const convo = conversation([message({ role: 'assistant', content: 'Chào bạn' })])
    expect(conversationTitle(convo)).toBe('Phiên verify-1')
  })

  it('maps the first user intent to a Vietnamese label', () => {
    const convo = conversation([
      message({ role: 'user', content: 'đặt gas', intent: 'place_order' }),
    ])
    expect(conversationIntent(convo)).toBe('Đặt hàng')
  })

  it('reports the most recent activity timestamp', () => {
    const convo = conversation([
      message({ content: 'a', created_at: '2026-06-13T10:00:00.000Z' }),
      message({ content: 'b', created_at: '2026-06-13T10:03:00.000Z' }),
    ])
    expect(conversationLastActivity(convo)).toBe('2026-06-13T10:03:00.000Z')
  })

  it('matches the status / emergency / flagged filters', () => {
    const escalated = conversation([message({ content: 'hi' })], 'escalated')
    const emergency = conversation([message({ content: 'mùi gas', is_emergency: true })])
    const flagged = conversation([message({ content: 'hmm', flagged_for_review: true })])

    expect(matchesChatFilter(escalated, 'escalated')).toBe(true)
    expect(matchesChatFilter(emergency, 'emergency')).toBe(true)
    expect(matchesChatFilter(flagged, 'flagged')).toBe(true)
    expect(matchesChatFilter(escalated, 'emergency')).toBe(false)
    expect(matchesChatFilter(emergency, 'all')).toBe(true)
  })

  it('searches session id, phone and message text', () => {
    const convo = conversation([message({ content: 'Cho hỏi giá gas 0903026306' })])
    expect(matchesConversationSearch(convo, '')).toBe(true)
    expect(matchesConversationSearch(convo, 'verify-12008')).toBe(true)
    expect(matchesConversationSearch(convo, '0903026306')).toBe(true)
    expect(matchesConversationSearch(convo, 'giá gas')).toBe(true)
    expect(matchesConversationSearch(convo, 'không có')).toBe(false)
  })

  it('formats Vietnamese relative time', () => {
    const now = Date.parse('2026-06-13T10:00:00.000Z')
    expect(relativeTime('2026-06-13T09:59:30.000Z', now)).toBe('Vừa xong')
    expect(relativeTime('2026-06-13T09:30:00.000Z', now)).toBe('30 phút trước')
    expect(relativeTime('2026-06-13T07:00:00.000Z', now)).toBe('3 giờ trước')
    expect(relativeTime('2026-06-11T10:00:00.000Z', now)).toBe('2 ngày trước')
  })

  it('extracts the latest staff follow-up note from message metadata', () => {
    const convo = conversation([
      message({ role: 'user', content: 'gọi lại 7-8h sáng mai' }),
      message({
        role: 'assistant',
        content: 'Dạ Qiki đã ghi chú gọi lại.',
        retrieved_documents: [
          {
            type: 'chat_followup_note',
            note_type: 'callback',
            time_window: '7-8h sáng mai',
            declined_callback: false,
            staff_reminder: 'Gọi lại 7-8h sáng mai',
          },
        ],
      }),
    ])
    const note = conversationFollowupNote(convo)
    expect(note).not.toBeNull()
    expect(note?.noteType).toBe('callback')
    expect(note?.staffReminder).toBe('Gọi lại 7-8h sáng mai')
    expect(note?.declinedCallback).toBe(false)
  })

  it('returns null when there is no follow-up note', () => {
    const convo = conversation([message({ role: 'user', content: 'giá gas bao nhiêu' })])
    expect(conversationFollowupNote(convo)).toBeNull()
  })
})
