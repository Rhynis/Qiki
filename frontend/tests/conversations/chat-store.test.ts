import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { STALE_SESSION_MS, useChatStore } from '@/lib/stores/chat-store'

const NOW = new Date('2026-06-11T10:00:00.000Z').getTime()

describe('chat store', () => {
  beforeEach(() => {
    vi.spyOn(Date, 'now').mockReturnValue(NOW)
    localStorage.clear()
    useChatStore.setState({
      isOpen: false,
      sessionId: 'session-a',
      conversationId: 'conversation-a',
      lastActivityAt: Date.now(),
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('keeps a fresh session when checking stale state', () => {
    useChatStore.setState({
      sessionId: 'session-a',
      conversationId: 'conversation-a',
      lastActivityAt: Date.now() - STALE_SESSION_MS + 1_000,
    })

    useChatStore.getState().startIfStale()

    expect(useChatStore.getState().sessionId).toBe('session-a')
    expect(useChatStore.getState().conversationId).toBe('conversation-a')
  })

  it('resets a stale session after two hours idle', () => {
    useChatStore.setState({
      sessionId: 'session-a',
      conversationId: 'conversation-a',
      lastActivityAt: Date.now() - STALE_SESSION_MS - 1_000,
    })

    useChatStore.getState().startIfStale()

    expect(useChatStore.getState().sessionId).not.toBe('session-a')
    expect(useChatStore.getState().conversationId).toBeUndefined()
    expect(useChatStore.getState().lastActivityAt).toBe(Date.now())
  })

  it('resets session manually and refreshes activity timestamp', () => {
    useChatStore.setState({
      sessionId: 'session-a',
      conversationId: 'conversation-a',
      lastActivityAt: Date.now() - 30_000,
    })

    useChatStore.getState().resetSession()

    expect(useChatStore.getState().sessionId).not.toBe('session-a')
    expect(useChatStore.getState().conversationId).toBeUndefined()
    expect(useChatStore.getState().lastActivityAt).toBe(Date.now())
  })
})
