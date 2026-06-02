import { describe, expect, it } from 'vitest'
import { reconcileMessageList } from '@/lib/hooks/use-conversation'
import type { Message, MessageListResponse } from '@/types/conversation'

function message(overrides: Partial<Message> & Pick<Message, 'id' | 'content'>): Message {
  return {
    conversation_id: 'conversation-1',
    role: 'user',
    flagged_for_review: false,
    is_emergency: false,
    created_at: '2026-06-01T08:00:00.000Z',
    ...overrides,
  }
}

function list(items: Message[]): MessageListResponse {
  return {
    items,
    total: items.length,
    skip: 0,
    limit: 50,
  }
}

describe('reconcileMessageList', () => {
  it('keeps known cache messages when a poll returns a stale list', () => {
    const first = message({ id: 'message-1', content: 'Xin chao' })
    const second = message({
      id: 'message-2',
      content: 'Toi can doi binh gas',
      created_at: '2026-06-01T08:01:00.000Z',
    })

    const result = reconcileMessageList(list([first]), list([first, second]))

    expect(result.items.map((item) => item.id)).toEqual(['message-1', 'message-2'])
    expect(result.total).toBe(2)
  })

  it('preserves local product cards when the server message omits them', () => {
    const serverMessage = message({
      id: 'assistant-1',
      role: 'assistant',
      content: 'Day la san pham phu hop',
    })
    const cachedMessage = {
      ...serverMessage,
      products: [
        {
          id: 'product-1',
          name: 'Gas 12kg',
          brand: 'Petrolimex',
          size_kg: 12,
          price: 450000,
          sku: 'GAS-12KG',
          stock_quantity: 5,
        },
      ],
    }

    const result = reconcileMessageList(list([serverMessage]), list([cachedMessage]))

    expect(result.items[0]?.products).toEqual(cachedMessage.products)
  })

  it('uses incoming server data for existing ids without duplicating messages', () => {
    const cachedMessage = message({
      id: 'message-1',
      content: 'Old content',
      feedback_score: null,
    })
    const incomingMessage = message({
      id: 'message-1',
      content: 'New content',
      feedback_score: 1,
    })

    const result = reconcileMessageList(list([incomingMessage]), list([cachedMessage]))

    expect(result.items).toHaveLength(1)
    expect(result.items[0]?.content).toBe('New content')
    expect(result.items[0]?.feedback_score).toBe(1)
  })
})
