/** SSE event payloads from POST /api/v1/chat/agent/stream (backend/app/agent). */

export type AgentStatusEvent = { session_id: string }

export type AgentTokenEvent = { type: 'token'; text: string }

export type AgentToolCallEvent = {
  tool_calls: Array<{ name: string; args: Record<string, unknown> }>
}

export type AgentNodeCompleteEvent = { node: string }

export type AgentDoneEvent = {
  session_id: string
  content: string
  llm_provider: string | null
}

export type AgentStreamRequest = {
  content: string
  session_id?: string
  locale?: 'vi' | 'en'
}
