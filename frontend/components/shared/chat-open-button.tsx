'use client'

import { MessageCircle } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { Button } from '@/components/ui/button'
import { useChatStore } from '@/lib/stores/chat-store'

type ChatOpenButtonProps = {
  className?: string
}

export function ChatOpenButton({ className }: ChatOpenButtonProps) {
  const t = useTranslations('shared')
  const open = useChatStore((state) => state.open)

  return (
    <Button className={className} size="lg" type="button" onClick={open}>
      <MessageCircle className="h-4 w-4" />
      {t('chatWithQiki')}
    </Button>
  )
}
