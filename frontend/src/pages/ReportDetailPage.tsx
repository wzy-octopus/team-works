import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { ThemeToggle } from '../components/ThemeToggle'
import type { WeeklyReport, WeeklyReportFeedback, ReactionType } from '../lib/types'

const REACTIONS: { type: ReactionType; emoji: string; label: string }[] = [
  { type: 'like', emoji: '👍', label: 'よくできました' },
  { type: 'star', emoji: '⭐', label: '今週のベスト' },
  { type: 'heart', emoji: '❤️', label: 'ありがとう' },
  { type: 'party', emoji: '🎉', label: 'おめでとう' },
  { type: 'muscle', emoji: '💪', label: '引き続き頑張れ' },
  { type: 'idea', emoji: '💡', label: '参考になりました' },
]

interface ReportWithUser extends WeeklyReport {
  user_name: string
  user_email: string
}

export function ReportDetailPage() {
  const { id } = useParams<{ id: string }>()
  const qc = useQueryClient()
  const [comment, setComment] = useState('')
  const [selectedReactions, setSelectedReactions] = useState<ReactionType[]>([])
  const [submitted, setSubmitted] = useState(false)

  const { data: report } = useQuery<ReportWithUser>({
    queryKey: ['report', id],
    queryFn: async () => {
      const res = await api.get(`/weekly-reports/${id}`)
      return res.data
    },
    enabled: !!id,
  })

  const { data: feedback } = useQuery<WeeklyReportFeedback | null>({
    queryKey: ['feedback', id],
    queryFn: async () => {
      const res = await api.get(`/weekly-reports/${id}/feedback`)
      return res.data
    },
    enabled: !!id,
  })

  const sendFeedback = useMutation({
    mutationFn: () =>
      api.post(`/weekly-reports/${id}/feedback`, {
        comment: comment || null,
        reaction_types: selectedReactions,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['feedback', id] })
      qc.invalidateQueries({ queryKey: ['inbox'] })
      setSubmitted(true)
    },
  })

  function toggleReaction(type: ReactionType) {
    setSelectedReactions((prev) =>
      prev.includes(type) ? prev.filter((r) => r !== type) : [...prev, type]
    )
  }

  const hasFeedback = !!feedback || submitted
  const canSend = !hasFeedback && (selectedReactions.length > 0 || comment.trim())

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <Link
            to={report ? `/inbox?week=${report.week_start_date}` : '/inbox'}
            className="text-gray-700 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white text-sm"
          >
            ← 受信トレイ
          </Link>
          {report && (
            <>
              <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center text-white font-semibold">
                {report.user_name?.[0]}
              </div>
              <div>
                <span className="text-[var(--text-primary)] font-medium">{report.user_name}</span>
                <span className="text-gray-700 dark:text-gray-400 text-sm ml-2">{report.week_start_date} 週</span>
              </div>
            </>
          )}
        </div>
        <ThemeToggle />
      </div>

      {!report ? (
        <div className="text-gray-700 dark:text-gray-400 text-center py-16">読み込み中...</div>
      ) : (
        <div className="grid grid-cols-3 gap-6">
          {/* Left */}
          <div className="col-span-2 space-y-5">
            <div className="bg-[var(--bg-surface)] rounded-xl p-5 border border-[var(--border)]">
              <h2 className="text-[var(--text-primary)] font-semibold mb-3">🤖 AIサマリ</h2>
              <p className="text-gray-700 dark:text-gray-300 text-sm leading-relaxed whitespace-pre-wrap">
                {report.ai_summary ?? 'AIサマリなし'}
              </p>
            </div>

            {[
              { key: 'feeling', label: '今週の所感' },
              { key: 'questions', label: '疑問・気になった点' },
              { key: 'issues', label: '課題・改善提案' },
            ].map(({ key, label }) => {
              const value = (report as unknown as Record<string, string | null>)[key]
              if (!value) return null
              return (
                <div key={key} className="bg-[var(--bg-surface)] rounded-xl p-5 border border-[var(--border)]">
                  <h3 className="text-gray-700 dark:text-gray-400 text-sm mb-2">{label}</h3>
                  <p className="text-[var(--text-primary)] text-sm leading-relaxed whitespace-pre-wrap">{value}</p>
                </div>
              )
            })}
          </div>

          {/* Right */}
          <div className="space-y-4">
            <div className="bg-[var(--bg-surface)] rounded-xl p-5 border border-[var(--border)]">
              <h3 className="text-[var(--text-primary)] font-semibold mb-4">フィードバック</h3>

              {hasFeedback ? (
                <div className="space-y-3">
                  <div className="flex flex-wrap gap-2">
                    {(feedback?.reactions ?? selectedReactions).map((r) => {
                      const rx = REACTIONS.find((x) => x.type === r)
                      return rx ? (
                        <span
                          key={r}
                          className="flex items-center gap-1 px-2 py-1 rounded-full bg-indigo-900/50 text-sm border border-indigo-500/30"
                        >
                          {rx.emoji} <span className="text-indigo-300 text-xs">{rx.label}</span>
                        </span>
                      ) : null
                    })}
                  </div>
                  {feedback?.comment && (
                    <p className="text-gray-700 dark:text-gray-300 text-sm bg-[var(--bg-input)] rounded-lg p-3">{feedback.comment}</p>
                  )}
                  {submitted && !feedback && (
                    <p className="text-green-400 text-sm">フィードバックを送信しました ✓</p>
                  )}
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-3 gap-2 mb-4">
                    {REACTIONS.map((r) => (
                      <button
                        key={r.type}
                        onClick={() => toggleReaction(r.type)}
                        className={`flex flex-col items-center gap-1 p-2 rounded-lg border transition-all text-xs ${
                          selectedReactions.includes(r.type)
                            ? 'border-indigo-500 bg-indigo-900/40 text-indigo-300'
                            : 'border-[var(--border)] text-gray-700 dark:text-gray-400 hover:border-gray-400 dark:hover:border-white/30'
                        }`}
                        title={r.label}
                      >
                        <span className="text-xl">{r.emoji}</span>
                        <span>{r.label}</span>
                      </button>
                    ))}
                  </div>
                  <textarea
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    rows={3}
                    placeholder="コメントを入力（任意）..."
                    className="w-full bg-[var(--bg-input)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:border-indigo-500 resize-none mb-3"
                  />
                  <button
                    onClick={() => sendFeedback.mutate()}
                    disabled={!canSend || sendFeedback.isPending}
                    className="w-full py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-sm font-medium transition-colors"
                  >
                    {sendFeedback.isPending ? '送信中...' : 'フィードバックを送信'}
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
