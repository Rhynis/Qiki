import { parseSseFrames } from '@/lib/api/conversations'
import type { AgentDoneEvent, AgentStreamRequest, AgentToolCallEvent } from '@/types/agent'

export type AgentStreamHandlers = {
  onToken: (text: string) => void
  onToolCall?: (event: AgentToolCallEvent) => void
  onDone: (event: AgentDoneEvent) => void
}

/**
 * Stream one turn from the LangGraph agent endpoint. Mirrors
 * `conversations.streamMessage`'s fetch + SSE-frame-parsing shape (reusing its
 * exported `parseSseFrames`), but for the agent's distinct event vocabulary
 * (`status`/`token`/`tool_call`/`node_complete`/`done`) and response shape —
 * the agent MVP has no persisted Conversation/Message rows to reconcile
 * against (the LangGraph checkpointer is the persistence layer instead).
 */
export async function streamAgentTurn(
  data: AgentStreamRequest,
  handlers: AgentStreamHandlers,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch('/api/v1/chat/agent/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
    signal,
  })
  if (!response.ok || !response.body) {
    throw new Error(`Agent streaming request failed with status ${response.status}`)
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let receivedDone = false
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const { frames, rest } = parseSseFrames(buffer)
    buffer = rest
    for (const frame of frames) {
      if (frame.event === 'token') {
        handlers.onToken((JSON.parse(frame.data) as { text: string }).text)
      } else if (frame.event === 'tool_call') {
        handlers.onToolCall?.(JSON.parse(frame.data) as AgentToolCallEvent)
      } else if (frame.event === 'done') {
        receivedDone = true
        handlers.onDone(JSON.parse(frame.data) as AgentDoneEvent)
      }
      // 'status' / 'node_complete' are informational only — nothing to do yet.
    }
  }
  if (!receivedDone) {
    throw new Error('Agent stream ended before the final event')
  }
}
