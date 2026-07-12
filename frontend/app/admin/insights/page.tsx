'use client'

import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { PageHeader } from '@/components/shared/page-header'
import { getInsights } from '@/lib/api/insights'

function percent(value: number): string {
  return `${Math.round(value * 100)}%`
}

export default function AdminInsightsPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin-insights'],
    queryFn: () => getInsights(),
  })

  if (isLoading) {
    return <p className="p-4 text-sm text-slate-600">Đang tải thống kê...</p>
  }
  if (isError || !data) {
    return <p className="p-4 text-sm text-red-700">Không thể tải thống kê hội thoại.</p>
  }

  const { summary } = data
  const stats: Array<{ label: string; value: string }> = [
    { label: 'Hội thoại', value: String(summary.total_conversations) },
    { label: 'Tin nhắn', value: String(summary.total_messages) },
    { label: 'Tỷ lệ chuyển nhân viên', value: percent(summary.escalation_rate) },
    { label: 'Tỷ lệ gắn cờ', value: percent(summary.flag_rate) },
    { label: 'Tin độ tin cậy thấp', value: String(summary.low_confidence_messages) },
    { label: 'Phản hồi tiêu cực', value: String(summary.negative_feedback_messages) },
    { label: 'Chưa trả lời được', value: String(summary.unanswered_messages) },
    { label: 'Tin gắn cờ', value: String(summary.flagged_messages) },
  ]

  return (
    <div className="space-y-8">
      <PageHeader
        title="Thống kê hội thoại"
        description="Phân tích chat để cải thiện Knowledge Base và câu trả lời của Qiki (30 ngày gần nhất)."
      />

      <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {stats.map((stat) => (
          <div key={stat.label} className="rounded-lg border bg-white p-4">
            <p className="text-sm text-slate-600">{stat.label}</p>
            <p className="mt-1 text-2xl font-semibold">{stat.value}</p>
          </div>
        ))}
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-lg border bg-white p-4">
          <h2 className="mb-3 text-base font-semibold">Ý định phổ biến</h2>
          {data.top_intents.length === 0 ? (
            <p className="text-sm text-slate-500">Chưa có dữ liệu.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {data.top_intents.map((intent) => (
                <li key={intent.intent} className="flex justify-between">
                  <span>{intent.intent}</span>
                  <span className="font-medium">{intent.count}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="rounded-lg border bg-white p-4">
          <h2 className="mb-3 text-base font-semibold">Câu hỏi thường gặp</h2>
          {data.top_questions.length === 0 ? (
            <p className="text-sm text-slate-500">Chưa có dữ liệu.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {data.top_questions.map((theme) => (
                <li key={theme.question} className="flex justify-between gap-3">
                  <span className="min-w-0 truncate">{theme.question}</span>
                  <span className="shrink-0 font-medium">{theme.count}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="rounded-lg border bg-white p-4">
        <h2 className="mb-1 text-base font-semibold">Câu hỏi có thể thiếu trong Knowledge Base</h2>
        <p className="mb-3 text-sm text-slate-600">
          Những câu Qiki trả lời với độ tin cậy thấp, thiếu ngữ cảnh hoặc từ chối — ưu tiên bổ sung
          KB.
        </p>
        {data.knowledge_gaps.length === 0 ? (
          <p className="text-sm text-slate-500">Không phát hiện lỗ hổng nào trong kỳ này.</p>
        ) : (
          <ul className="divide-y">
            {data.knowledge_gaps.map((gap) => (
              <li key={gap.message_id} className="flex items-start justify-between gap-3 py-3">
                <div className="min-w-0">
                  <p className="truncate font-medium">{gap.question}</p>
                  <p className="text-xs text-slate-500">
                    {gap.reason}
                    {gap.intent ? ` · ${gap.intent}` : ''}
                    {gap.intent_confidence != null
                      ? ` · ${percent(gap.intent_confidence)}`
                      : ''}
                  </p>
                </div>
                <Link
                  className="shrink-0 text-sm text-primary hover:underline"
                  href={`/admin/chat/${gap.conversation_id}`}
                >
                  Xem hội thoại
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
