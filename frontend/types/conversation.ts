export type ConversationStatus = 'active' | 'escalated' | 'resolved' | 'abandoned'
export type MessageRole = 'user' | 'assistant' | 'staff' | 'system'

export type ProductCard = {
  id: string
  name: string
  brand: string
  size_kg: number | string
  price: number | string
  image_url?: string | null
  sku: string
  stock_quantity: number
}

export type Message = {
  id: string
  conversation_id: string
  role: MessageRole
  content: string
  intent?: string | null
  intent_confidence?: number | null
  llm_provider?: string | null
  llm_model?: string | null
  tokens_used?: number | null
  latency_ms?: number | null
  retrieved_documents?: Array<Record<string, unknown>> | null
  feedback_score?: -1 | 0 | 1 | null
  flagged_for_review: boolean
  is_emergency: boolean
  products?: ProductCard[]
  created_at: string
}

export type Conversation = {
  id: string
  user_id?: string | null
  session_id: string
  status: ConversationStatus
  assigned_to?: string | null
  escalated_at?: string | null
  escalation_reason?: string | null
  resolved_at?: string | null
  satisfaction_rating?: number | null
  messages: Message[]
  created_at: string
  updated_at: string
}

export type ConversationListResponse = {
  items: Conversation[]
  total: number
  skip: number
  limit: number
}

export type MessageListResponse = {
  items: Message[]
  total: number
  skip: number
  limit: number
}

export type SendMessageResponse = {
  user_message: Message
  assistant_message?: Message | null
  conversation: Conversation
  products: ProductCard[]
}

export type StartConversationRequest = {
  session_id?: string
  initial_message?: string
}

export type SendMessageRequest = {
  content: string
  session_id?: string
}

export type FeedbackRequest = {
  score: -1 | 0 | 1
}

export type StaffMessageRequest = {
  content: string
}

export type TransferRequest = {
  staff_id: string
}

export type ResolveRequest = {
  satisfaction_rating?: number | null
}
