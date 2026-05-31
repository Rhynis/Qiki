'use client'

import { SendHorizonal } from 'lucide-react'
import { FormEvent, KeyboardEvent, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

type MessageInputProps = {
  disabled?: boolean
  sending?: boolean
  onSend: (content: string) => void
}

export function MessageInput({ disabled, sending, onSend }: MessageInputProps) {
  const [content, setContent] = useState('')

  function submitMessage() {
    const trimmed = content.trim()
    if (!trimmed || disabled || sending) return
    onSend(trimmed)
    setContent('')
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    submitMessage()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== 'Enter' || event.shiftKey) return
    event.preventDefault()
    submitMessage()
  }

  return (
    <form className="flex gap-2 border-t bg-white p-3" onSubmit={handleSubmit}>
      <Textarea
        value={content}
        onChange={(event) => setContent(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Nhập tin nhắn..."
        className="min-h-10 resize-none"
        disabled={disabled}
        rows={1}
      />
      <Button type="submit" size="icon" disabled={disabled || sending || !content.trim()}>
        <SendHorizonal className="h-4 w-4" />
      </Button>
    </form>
  )
}
