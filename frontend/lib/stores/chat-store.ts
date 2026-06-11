'use client'

import { v4 as uuidv4 } from 'uuid'
import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'

export const STALE_SESSION_MS = 2 * 60 * 60 * 1000

type ChatState = {
  isOpen: boolean
  sessionId: string
  conversationId?: string
  lastActivityAt: number
  open: () => void
  close: () => void
  toggle: () => void
  setConversationId: (conversationId?: string) => void
  markActivity: () => void
  startIfStale: () => void
  resetSession: () => void
}

function freshSessionState(timestamp = Date.now()) {
  return {
    sessionId: uuidv4(),
    conversationId: undefined,
    lastActivityAt: timestamp,
  }
}

function isStale(lastActivityAt: number, timestamp = Date.now()) {
  return timestamp - lastActivityAt > STALE_SESSION_MS
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      isOpen: false,
      sessionId: uuidv4(),
      conversationId: undefined,
      lastActivityAt: Date.now(),
      open: () =>
        set((state) => {
          const timestamp = Date.now()
          if (isStale(state.lastActivityAt, timestamp)) {
            return { ...freshSessionState(timestamp), isOpen: true }
          }
          return { isOpen: true, lastActivityAt: timestamp }
        }),
      close: () => set({ isOpen: false }),
      toggle: () =>
        set((state) => {
          if (state.isOpen) return { isOpen: false }
          const timestamp = Date.now()
          if (isStale(state.lastActivityAt, timestamp)) {
            return { ...freshSessionState(timestamp), isOpen: true }
          }
          return { isOpen: true, lastActivityAt: timestamp }
        }),
      setConversationId: (conversationId) => set({ conversationId, lastActivityAt: Date.now() }),
      markActivity: () => set({ lastActivityAt: Date.now() }),
      startIfStale: () =>
        set((state) => {
          const timestamp = Date.now()
          if (!isStale(state.lastActivityAt, timestamp)) return {}
          return freshSessionState(timestamp)
        }),
      resetSession: () => set(() => freshSessionState()),
    }),
    {
      name: 'gasbot-chat',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        sessionId: state.sessionId,
        conversationId: state.conversationId,
        lastActivityAt: state.lastActivityAt,
      }),
    }
  )
)
