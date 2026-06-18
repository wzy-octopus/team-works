import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { ThemeToggle } from '../components/ThemeToggle'
import { useThemeStore } from '../stores/themeStore'
import { addDays, jstThisMonday } from '../lib/date'
import type { WeeklyReport, WeeklyReportFeedback, ReactionType } from '../lib/types'

const REACTIONS: { type: ReactionType; emoji: string; label: string }[] = [
  { type: 'like', emoji: '👍', label: 'よくできました' },
  { type: 'star', emoji: '⭐', label: '今週のベスト' },
  { type: 'heart', emoji: '❤️', label: 'ありがとう' },
  { type: 'party', emoji: '🎉', label: 'おめでとう' },
  { type: 'muscle', emoji: '💪', label: '引き続き頑張れ' },
  { type: 'idea', emoji: '💡', label: '参考になりました' },
]

const STATUS_LABELS: Record<string, string> = {
  draft: '下書き',
  ready: '提出可能',
  submitted: '提出済み',
  feedback_received: 'FB済み',
}
const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-700 text-gray-300',
  ready: 'bg-yellow-700 text-yellow-200',
  submitted: 'bg-blue-700 text-blue-200',
  feedback_received: 'bg-green-700 text-green-200',
}

export function WeeklyReportPage() {
  const qc = useQueryClient()
  const dark = useThemeStore((s) => s.dark)
  const textColor = dark ? '#ffffff' : '#111827'
  const [weekStart, setWeekStart] = useState(jstThisMonday())
  const [showSubmitModal, setShowSubmitModal] = useState(false)
  const [fieldValues, setFieldValues] = useState({ feeling: '', questions: '', issues: '' })

  const { data: report, isLoading } = useQuery<WeeklyReport | null>({
    queryKey: ['weekly-report', weekStart],
    queryFn: async () => {
      const res = await api.get(`/weekly-reports/current?week_start_date=${weekStart}`)
      return res.data
    },
  })

  useEffect(() => {
    // report.id / weekStart 変更時のみフォームへ同期する意図的な処理（入力中の上書きを防ぐ）
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setFieldValues({
      feeling: report?.feeling ?? '',
      questions: report?.questions ?? '',
      issues: report?.issues ?? '',
    })
  // report.id か weekStart が変わったときだけ同期（入力中に上書きしないため）
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [report?.id, weekStart])

  const updateReport = useMutation({
    mutationFn: (data: Partial<WeeklyReport>) =>
      report
        ? api.patch(`/weekly-reports/${report.id}`, data)
        : api.post('/weekly-reports', { week_start_date: weekStart, ...data }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['weekly-report'] }),
  })

  const submitReport = useMutation({
    mutationFn: () => api.post(`/weekly-reports/${report!.id}/submit`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['weekly-report'] })
      setShowSubmitModal(true)
    },
  })

  const regenerate = useMutation({
    mutationFn: () => api.post(`/weekly-reports/${report!.id}/regenerate-summary`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['weekly-report'] }),
  })

  const { data: feedback } = useQuery<WeeklyReportFeedback | null>({
    queryKey: ['weekly-report-feedback', report?.id],
    queryFn: async () => {
      const res = await api.get(`/weekly-reports/${report!.id}/feedback`)
      return res.data
    },
    enabled: !!report?.id,
  })

  function shiftWeek(delta: number) {
    setWeekStart(addDays(weekStart, delta * 7))
  }

  const weekEnd = addDays(weekStart, 6)

  const isSubmitted = report?.status === 'submitted' || report?.status === 'feedback_received'
  const canSubmit = !!report?.feeling && !isSubmitted

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">週間レポート</h1>
          {report && (
            <span className={`text-xs px-2 py-1 rounded-full ${STATUS_COLORS[report.status]}`}>
              {STATUS_LABELS[report.status]}
            </span>
          )}
        </div>
        <ThemeToggle />
      </div>

      {/* Week navigator */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => shiftWeek(-1)} className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1">‹</button>
        <span className="text-[var(--text-primary)] text-sm">
          {weekStart} 〜 {weekEnd}
        </span>
        <button onClick={() => shiftWeek(1)} className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1">›</button>
      </div>

      {isLoading ? (
        <div className="text-gray-400 text-center py-16">読み込み中...</div>
      ) : (
        <div className="grid grid-cols-3 gap-6">
          {/* Left column */}
          <div className="col-span-2 space-y-5">
            {/* AI summary */}
            <div className="bg-[var(--bg-surface)] rounded-xl p-5 border border-[var(--border)]">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-[var(--text-primary)] font-semibold">🤖 AIサマリ</h2>
                {report && !isSubmitted && (
                  <button
                    onClick={() => regenerate.mutate()}
                    disabled={regenerate.isPending}
                    className="text-indigo-400 hover:text-indigo-300 text-xs border border-indigo-500/30 px-2 py-1 rounded disabled:opacity-50"
                  >
                    {regenerate.isPending ? '生成中...' : '再生成'}
                  </button>
                )}
              </div>
              {report?.ai_summary ? (
                <p className="text-[var(--text-primary)] text-sm leading-relaxed whitespace-pre-wrap">{report.ai_summary}</p>
              ) : (
                <p className="text-gray-500 text-sm italic">
                  {report ? 'AIサマリ未生成です。「再生成」をクリックしてください。' : '週報がまだ作成されていません。'}
                </p>
              )}
            </div>

            {/* Feeling & optional fields */}
            {['feeling', 'questions', 'issues'].map((field) => {
              const labels: Record<string, { title: string; required: boolean; placeholder: string }> = {
                feeling: { title: '今週の所感', required: true, placeholder: '今週の振り返りを記入...' },
                questions: { title: '疑問・気になった点', required: false, placeholder: '確認したいことや気になった点...' },
                issues: { title: '課題・改善提案', required: false, placeholder: '来週以降への提言...' },
              }
              const { title, required, placeholder } = labels[field]
              const value = fieldValues[field as keyof typeof fieldValues]

              return (
                <div key={field} className="bg-[var(--bg-surface)] rounded-xl p-5 border border-[var(--border)]">
                  <div className="flex items-center gap-2 mb-3">
                    <h3 className="text-[var(--text-primary)] font-medium text-sm">{title}</h3>
                    {required && <span className="text-red-400 text-xs">必須</span>}
                  </div>
                  {isSubmitted ? (
                    <p
                      style={{ color: textColor }}
                      className="text-sm leading-relaxed whitespace-pre-wrap min-h-[4.5rem] bg-[var(--bg-input)] border border-[var(--border)] rounded-lg px-3 py-2"
                    >
                      {value || <span className="text-gray-400 italic">{placeholder}</span>}
                    </p>
                  ) : (
                    <textarea
                      value={value}
                      onChange={(e) =>
                        setFieldValues((prev) => ({ ...prev, [field]: e.target.value }))
                      }
                      onBlur={() => updateReport.mutate({ [field]: value })}
                      rows={3}
                      placeholder={placeholder}
                      style={{ color: textColor }}
                      className="w-full bg-[var(--bg-input)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm placeholder-gray-400 focus:outline-none focus:border-indigo-500 resize-none"
                    />
                  )}
                  {field === 'feeling' && (
                    <p className="text-gray-500 text-xs mt-1 text-right">{value.length} 文字</p>
                  )}
                </div>
              )
            })}
          </div>

          {/* Right sidebar */}
          <div className="space-y-4">
            {/* Feedback from manager */}
            {feedback && (
              <div className="bg-[var(--bg-surface)] rounded-xl p-5 border border-indigo-500/30">
                <h3 className="text-[var(--text-primary)] font-semibold mb-3">上司からのフィードバック</h3>
                {feedback.reactions.length > 0 && (
                  <div className="flex flex-wrap gap-2 mb-3">
                    {feedback.reactions.map((r) => {
                      const rx = REACTIONS.find((x) => x.type === r)
                      return rx ? (
                        <span key={r} className="flex items-center gap-1 px-2 py-1 rounded-full bg-indigo-900/50 text-sm border border-indigo-500/30">
                          {rx.emoji} <span className="text-indigo-300 text-xs">{rx.label}</span>
                        </span>
                      ) : null
                    })}
                  </div>
                )}
                {feedback.comment && (
                  <p className="text-[var(--text-primary)] text-sm bg-[var(--bg-input)] rounded-lg p-3 leading-relaxed whitespace-pre-wrap">
                    {feedback.comment}
                  </p>
                )}
                <p className="text-gray-500 text-xs mt-2 text-right">
                  {new Date(feedback.created_at).toLocaleDateString('ja-JP')}
                </p>
              </div>
            )}

            <div className="bg-[var(--bg-surface)] rounded-xl p-5 border border-[var(--border)]">
              <h3 className="text-[var(--text-primary)] font-semibold mb-4">提出</h3>
              <div className="space-y-2 mb-4">
                {[
                  { label: 'AIサマリ生成済み', done: !!report?.ai_summary },
                  { label: '今週の所感を記入', done: !!report?.feeling },
                ].map((item) => (
                  <div key={item.label} className="flex items-center gap-2 text-sm">
                    <span className={item.done ? 'text-green-400' : 'text-gray-500'}>
                      {item.done ? '✓' : '○'}
                    </span>
                    <span className={item.done ? 'text-[var(--text-primary)]' : 'text-[var(--text-muted)]'}>{item.label}</span>
                  </div>
                ))}
              </div>
              <button
                onClick={() => submitReport.mutate()}
                disabled={!canSubmit || submitReport.isPending}
                className="w-full py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors mb-2"
              >
                {isSubmitted ? '提出済み' : submitReport.isPending ? '提出中...' : '週報を提出する'}
              </button>
              {!isSubmitted && (
                <button
                  onClick={() => updateReport.mutate({})}
                  className="w-full py-2 rounded-lg border border-[var(--border)] text-[var(--text-muted)] hover:text-[var(--text-primary)] text-sm transition-colors"
                >
                  下書きとして保存
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Submit modal */}
      {showSubmitModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-[var(--bg-surface)] rounded-2xl p-8 border border-[var(--border)] text-center max-w-sm mx-4">
            <div className="text-5xl mb-4">🎉</div>
            <h3 className="text-[var(--text-primary)] text-xl font-bold mb-2">週報を提出しました！</h3>
            <p className="text-gray-400 text-sm mb-6">上長に通知が送られました。</p>
            <button
              onClick={() => setShowSubmitModal(false)}
              className="px-6 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-500"
            >
              閉じる
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
