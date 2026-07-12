import { apiClient } from '@/lib/api/client'

export interface IntentCount {
  intent: string
  count: number
}

export interface QuestionTheme {
  question: string
  count: number
}

export interface TrendPoint {
  date: string
  conversations: number
  flagged: number
  escalated: number
}

export interface KnowledgeGapQuestion {
  conversation_id: string
  message_id: string
  question: string
  intent: string | null
  intent_confidence: number | null
  reason: string
  created_at: string
}

export interface InsightsSummary {
  total_conversations: number
  total_messages: number
  user_messages: number
  assistant_messages: number
  escalated_conversations: number
  flagged_messages: number
  low_confidence_messages: number
  negative_feedback_messages: number
  unanswered_messages: number
  escalation_rate: number
  flag_rate: number
}

export interface ConversationInsights {
  period_start: string
  period_end: string
  summary: InsightsSummary
  top_intents: IntentCount[]
  top_questions: QuestionTheme[]
  trend: TrendPoint[]
  knowledge_gaps: KnowledgeGapQuestion[]
}

export async function getInsights(params?: {
  date_from?: string
  date_to?: string
}): Promise<ConversationInsights> {
  const response = await apiClient.get<ConversationInsights>('/api/v1/admin/insights', {
    params,
  })
  return response.data
}
