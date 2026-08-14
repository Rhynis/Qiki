'use client'

import { MessageCircle } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { useChatStore } from '@/lib/stores/chat-store'
import { AgentChatWindow } from './agent-chat-window'
import { ChatWindow } from './chat-window'

// Mirrors the backend AGENT_ENABLED flag (default off). Next.js inlines
// NEXT_PUBLIC_* vars at build time, so this never adds a runtime branch cost
// when unset — the default customer-facing ChatWindow is unaffected either way.
const AGENT_ENABLED = process.env.NEXT_PUBLIC_AGENT_ENABLED === 'true'

export function ChatWidget() {
  const t = useTranslations('chat')
  const isOpen = useChatStore((state) => state.isOpen)
  const toggle = useChatStore((state) => state.toggle)

  return (
    <>
      {isOpen ? AGENT_ENABLED ? <AgentChatWindow /> : <ChatWindow /> : null}
      <Button
        type="button"
        size="icon"
        className="fixed bottom-6 right-4 z-50 h-14 w-14 rounded-full shadow-lg md:right-6"
        aria-label={t('openAria')}
        onClick={toggle}
      >
        <MessageCircle className="h-6 w-6" />
      </Button>
    </>
  )
}
