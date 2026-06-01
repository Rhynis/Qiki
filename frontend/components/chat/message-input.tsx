'use client'

import { SendHorizonal } from 'lucide-react'
import { FormEvent, KeyboardEvent, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

type MessageInputProps = {
  disabled?: boolean
  rateLimited?: boolean
  sending?: boolean
  onSend: (content: string) => boolean
}

export function MessageInput({ disabled, rateLimited, sending, onSend }: MessageInputProps) {
  const [content, setContent] = useState('')

  function submitMessage() {
    const trimmed = content.trim()
    if (!trimmed || disabled || rateLimited || sending) return
    if (onSend(trimmed)) setContent('')
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    submitMessage()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.nativeEvent.isComposing || event.keyCode === 229) return
    if (event.key !== 'Enter' || event.shiftKey) return
    event.preventDefault()
    submitMessage()
  }

  return (
    <form className="border-t bg-white p-3" onSubmit={handleSubmit}>
      <div className="flex gap-2">
        <Textarea
          value={content}
          onChange={(event) => setContent(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Nhập tin nhắn..."
          className="min-h-10 resize-none"
          disabled={disabled}
          rows={1}
        />
        <Button
          type="submit"
          size="icon"
          disabled={disabled || rateLimited || sending || !content.trim()}
        >
          <SendHorizonal className="h-4 w-4" />
        </Button>
      </div>
      {rateLimited ? (
        <p className="mt-2 text-xs text-slate-500">Bạn gửi hơi nhanh, vui lòng đợi vài giây.</p>
      ) : null}
    </form>
  )
}
