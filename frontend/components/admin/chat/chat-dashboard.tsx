'use client'

import { AlertTriangle, Flag, MessageSquareText, RefreshCw, Search } from 'lucide-react'
import Link from 'next/link'
import { useMemo, useState } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { useStaffConversations } from '@/lib/hooks/use-conversation'
import { cn } from '@/lib/utils'
import {
  type ChatFilter,
  conversationHasEmergency,
  conversationHasFlag,
  conversationIntent,
  conversationLastActivity,
  conversationLastText,
  conversationTitle,
  matchesChatFilter,
  matchesConversationSearch,
  relativeTime,
} from '@/lib/utils/conversation-summary'

const LIST_CAP = 100

const statusLabels: Record<string, string> = {
  active: 'Đang hoạt động',
  escalated: 'Cần hỗ trợ',
  resolved: 'Đã xử lý',
  abandoned: 'Bỏ dở',
}

const filters: Array<{ value: ChatFilter; label: string }> = [
  { value: 'escalated', label: 'Cần hỗ trợ' },
  { value: 'emergency', label: 'Khẩn cấp' },
  { value: 'flagged', label: 'Bị flag' },
  { value: 'all', label: 'Tất cả' },
]

export function ChatDashboard() {
  // Fetch broadly (recent-first) and filter/search/sort in the UI — no data is deleted.
  const conversations = useStaffConversations({ limit: LIST_CAP })
  const [filter, setFilter] = useState<ChatFilter>('escalated')
  const [search, setSearch] = useState('')

  const items = useMemo(() => conversations.data?.items ?? [], [conversations.data])

  const counts = useMemo(
    () => ({
      escalated: items.filter((item) => item.status === 'escalated').length,
      emergency: items.filter(conversationHasEmergency).length,
      flagged: items.filter(conversationHasFlag).length,
    }),
    [items]
  )

  const visible = useMemo(
    () =>
      items
        .filter((item) => matchesChatFilter(item, filter))
        .filter((item) => matchesConversationSearch(item, search))
        .sort(
          (left, right) =>
            Date.parse(conversationLastActivity(right)) - Date.parse(conversationLastActivity(left))
        ),
    [items, filter, search]
  )

  if (conversations.isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Chat hỗ trợ</h1>
          <p className="text-sm text-slate-600">Cuộc trò chuyện gần đây cần theo dõi</p>
        </div>
        <Button type="button" variant="outline" onClick={() => conversations.refetch()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Làm mới
        </Button>
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <StatCard label="Cần hỗ trợ" value={counts.escalated} />
        <StatCard label="Khẩn cấp" value={counts.emergency} tone="text-red-700" />
        <StatCard label="Bị flag" value={counts.flagged} tone="text-amber-700" />
      </div>

      <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-white p-3">
        <div className="flex flex-wrap gap-1">
          {filters.map((option) => (
            <Button
              key={option.value}
              type="button"
              size="sm"
              variant={filter === option.value ? 'default' : 'outline'}
              onClick={() => setFilter(option.value)}
            >
              {option.label}
            </Button>
          ))}
        </div>
        <div className="relative min-w-[200px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
          <Input
            className="pl-9"
            placeholder="Tìm theo session, SĐT hoặc nội dung"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
      </div>

      <div className="space-y-2">
        {visible.length ? (
          visible.map((conversation) => {
            const hasEmergency = conversationHasEmergency(conversation)
            const hasFlag = conversationHasFlag(conversation)
            const intent = conversationIntent(conversation)
            return (
              <Link
                key={conversation.id}
                href={`/admin/chat/${conversation.id}`}
                className="block rounded-lg border bg-white p-4 transition hover:border-slate-400"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 space-y-1">
                    <div className="flex items-center gap-2">
                      <MessageSquareText className="h-4 w-4 shrink-0 text-slate-500" />
                      <p className="truncate text-sm font-semibold text-slate-900">
                        {conversationTitle(conversation)}
                      </p>
                      {intent ? (
                        <Badge variant="outline" className="shrink-0 text-xs font-normal">
                          {intent}
                        </Badge>
                      ) : null}
                    </div>
                    <p className="truncate text-sm text-slate-600">
                      {conversationLastText(conversation)}
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <span className="text-xs text-slate-500">
                      {relativeTime(conversationLastActivity(conversation))}
                    </span>
                    <div className="flex items-center gap-2">
                      {hasEmergency ? <AlertTriangle className="h-4 w-4 text-red-700" /> : null}
                      {hasFlag ? <Flag className="h-4 w-4 text-amber-700" /> : null}
                      <Badge
                        variant="outline"
                        className={cn(
                          conversation.status === 'escalated' && 'border-sky-300 text-sky-800',
                          conversation.status === 'resolved' &&
                            'border-emerald-300 text-emerald-800'
                        )}
                      >
                        {statusLabels[conversation.status] ?? conversation.status}
                      </Badge>
                    </div>
                  </div>
                </div>
              </Link>
            )
          })
        ) : (
          <div className="rounded-lg border bg-white p-10 text-center text-sm text-slate-500">
            Không có cuộc trò chuyện phù hợp bộ lọc.
          </div>
        )}
      </div>
    </div>
  )
}

function StatCard({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <div className="rounded-lg border bg-white p-4">
      <p className="text-sm font-medium text-slate-600">{label}</p>
      <p className={cn('mt-1 text-3xl font-semibold text-slate-900', tone)}>{value}</p>
    </div>
  )
}
