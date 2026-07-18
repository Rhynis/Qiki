'use client'

import { useTranslations } from 'next-intl'
import { useEffect, useRef } from 'react'
import { ScrollArea } from '@/components/ui/scroll-area'
import type { Message } from '@/types/conversation'
import { EmergencyBanner } from './emergency-banner'
import { MessageBubble } from './message-bubble'
import { TypingIndicator } from './typing-indicator'

type MessageListProps = {
  conversationId: string
  messages: Message[]
  isPending?: boolean
}

export function MessageList({ conversationId, messages, isPending }: MessageListProps) {
  const t = useTranslations('chat')
  const hasEmergency = messages.some((message) => message.is_emergency)
  const bottomRef = useRef<HTMLDivElement>(null)
  const lastMessageId = messages[messages.length - 1]?.id

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length, lastMessageId, isPending])

  return (
    <ScrollArea className="h-96">
      <div className="space-y-3 p-4">
        {hasEmergency ? <EmergencyBanner /> : null}
        {messages.length === 0 ? (
          <p className="py-10 text-center text-sm text-slate-500">{t('emptyPrompt')}</p>
        ) : (
          messages.map((message) => (
            <MessageBubble key={message.id} conversationId={conversationId} message={message} />
          ))
        )}
        {isPending ? <TypingIndicator /> : null}
        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  )
}
