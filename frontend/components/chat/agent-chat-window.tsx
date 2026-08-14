'use client'

import { Bot, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useAgentChat } from '@/lib/hooks/use-agent-chat'
import { useChatStore } from '@/lib/stores/chat-store'
import { MessageInput } from './message-input'
import { MessageList } from './message-list'

/**
 * Minimal opt-in window for the LangGraph agent path (AGENT_ENABLED /
 * NEXT_PUBLIC_AGENT_ENABLED). Rendered by ChatWidget INSTEAD OF ChatWindow
 * when the flag is on — the default customer-facing chat (ChatWindow) is
 * completely untouched and remains the only path when the flag is off.
 * Reuses MessageList/MessageInput for consistent rendering; state is local
 * (see useAgentChat) since this MVP has no persisted Conversation resource.
 */
export function AgentChatWindow() {
  const close = useChatStore((state) => state.close)
  const { messages, sendMessage, isStreaming, sessionId } = useAgentChat()

  return (
    <section className="fixed bottom-24 right-4 z-50 w-[calc(100vw-2rem)] max-w-md origin-bottom-right overflow-hidden rounded-lg border bg-slate-50 shadow-xl duration-200 ease-out animate-in fade-in zoom-in-95 slide-in-from-bottom-4 md:right-6">
      <header className="flex items-center justify-between border-b bg-slate-900 px-4 py-3 text-white">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5" />
          <div>
            <p className="text-sm font-semibold">Qiki (agent preview)</p>
            <p className="text-xs text-slate-300">LangGraph — {sessionId.slice(0, 8)}</p>
          </div>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="h-11 w-11 text-white hover:bg-slate-700"
          aria-label="Đóng"
          onClick={close}
        >
          <X className="h-4 w-4" />
        </Button>
      </header>
      <MessageList conversationId={sessionId} messages={messages} isPending={isStreaming} />
      <MessageInput sending={isStreaming} onSend={sendMessage} />
    </section>
  )
}
