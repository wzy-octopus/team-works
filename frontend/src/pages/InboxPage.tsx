import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import { ThemeToggle } from '../components/ThemeToggle'
import { addDays, jstThisMonday, mondayOf } from '../lib/date'
import type { InboxReport, WeeklyReportStatus } from '../lib/types'

const STATUS_LABELS: Record<WeeklyReportStatus, string> = {
  draft: '下書き',
  ready: '提出可能',
  submitted: '未読',
  feedback_received: 'FB済み',
}
const STATUS_COLORS: Record<WeeklyReportStatus, string> = {
  draft: 'text-gray-400 bg-gray-700',
  ready: 'text-yellow-300 bg-yellow-900',
  submitted: 'text-blue-300 bg-blue-900',
  feedback_received: 'text-green-300 bg-green-900',
}

// ?week= が有効な日付ならその週の月曜日、無効/未指定なら今週の月曜日（JST）。
// 週表示中の詳細画面から戻った時に元の週を維持するため、選択週は URL で持つ。
function resolveWeekStart(param: string | null): string {
  if (param && /^\d{4}-\d{2}-\d{2}$/.test(param) && !isNaN(new Date(`${param}T12:00:00Z`).getTime())) {
    return mondayOf(param)
  }
  return jstThisMonday()
}

export function InboxPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const weekStart = resolveWeekStart(searchParams.get('week'))
  const [filter, setFilter] = useState<'all' | 'submitted' | 'feedback_received' | 'pending'>('all')

  const { data: reports = [], isLoading } = useQuery<InboxReport[]>({
    queryKey: ['inbox', weekStart],
    queryFn: async () => {
      const res = await api.get('/weekly-reports/inbox', { params: { week_start_date: weekStart } })
      return res.data
    },
  })

  function shiftWeek(delta: number) {
    setSearchParams({ week: addDays(weekStart, delta * 7) }, { replace: true })
  }

  const weekEnd = addDays(weekStart, 6)

  const submitted = reports.filter((r) => r.status === 'submitted' || r.status === 'feedback_received')
  const unread = reports.filter((r) => r.status === 'submitted')
  const feedback = reports.filter((r) => r.status === 'feedback_received')
  const pending = reports.filter((r) => r.status === 'draft' || r.status === 'ready')

  const filtered =
    filter === 'all'
      ? reports
      : filter === 'submitted'
      ? submitted
      : filter === 'feedback_received'
      ? feedback
      : pending

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">週報受信トレイ</h1>
        </div>
        <ThemeToggle />
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: '未読', value: unread.length, color: 'text-blue-500 dark:text-blue-400' },
          { label: '提出済み', value: submitted.length, color: 'text-[var(--text-primary)]' },
          { label: '未提出', value: pending.length, color: 'text-yellow-600 dark:text-yellow-400' },
          { label: 'FB済み', value: feedback.length, color: 'text-green-500 dark:text-green-400' },
        ].map((c) => (
          <div key={c.label} className="bg-[var(--bg-surface)] rounded-xl p-4 border border-[var(--border)]">
            <p className="text-gray-700 dark:text-gray-400 text-xs mb-1">{c.label}</p>
            <p className={`text-3xl font-bold ${c.color}`}>{c.value}</p>
          </div>
        ))}
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex rounded-lg overflow-hidden border border-[var(--border)]">
          {(['all', 'submitted', 'feedback_received', 'pending'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 text-sm transition-colors ${
                filter === f ? 'bg-indigo-600 text-white' : 'text-gray-700 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
              }`}
            >
              {f === 'all' ? 'すべて' : f === 'submitted' ? '提出済み' : f === 'feedback_received' ? 'FB済み' : '未提出'}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 ml-auto">
          <button onClick={() => shiftWeek(-1)} className="text-gray-700 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white px-2">‹</button>
          <span className="text-gray-900 dark:text-white text-sm">{weekStart} 〜 {weekEnd}</span>
          <button onClick={() => shiftWeek(1)} className="text-gray-700 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white px-2">›</button>
        </div>
      </div>

      {/* Report list */}
      {isLoading ? (
        <div className="text-gray-700 dark:text-gray-400 text-center py-16">読み込み中...</div>
      ) : filtered.length === 0 ? (
        <div className="text-gray-700 dark:text-gray-400 text-center py-16">週報がありません</div>
      ) : (
        <div className="space-y-2">
          {filtered.map((r) => {
            const isPending = r.status === 'draft' || r.status === 'ready'
            const isUnread = r.status === 'submitted'
            return (
              <Link
                key={r.id}
                to={`/inbox/${r.id}`}
                className={`flex items-center gap-4 bg-[var(--bg-surface)] rounded-xl px-4 py-3 border transition-colors hover:border-indigo-500/50 ${
                  isPending
                    ? 'border-[var(--border-subtle)] opacity-60'
                    : isUnread
                    ? 'border-l-4 border-l-blue-500 border-y-[var(--border)] border-r-[var(--border)]'
                    : 'border-[var(--border)]'
                }`}
              >
                <div className="w-9 h-9 rounded-full bg-indigo-600 flex items-center justify-center text-white font-semibold shrink-0">
                  {r.user_name[0]}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className={`font-medium text-sm ${isUnread ? 'text-gray-900 dark:text-white' : 'text-gray-600 dark:text-gray-500'}`}>
                      {r.user_name}
                    </span>
                    <span className={`text-xs px-1.5 py-0.5 rounded ${STATUS_COLORS[r.status]}`}>
                      {STATUS_LABELS[r.status]}
                    </span>
                  </div>
                  <p className="text-gray-600 dark:text-gray-500 text-xs truncate">
                    {r.feeling ?? (isPending ? '未提出' : 'サマリなし')}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <p className="text-gray-600 dark:text-gray-500 text-xs">
                    {r.submitted_at ? new Date(r.submitted_at).toLocaleDateString('ja-JP') : '—'}
                  </p>
                </div>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
