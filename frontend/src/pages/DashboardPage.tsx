import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { useProjectStore } from '../stores/projectStore'
import { ThemeToggle } from '../components/ThemeToggle'
import type { DashboardTask } from '../lib/types'

type ViewMode = 'member' | 'kanban'

type DashboardResponse = {
  tasks: DashboardTask[]
  private_counts: Record<string, number>
}

const STATUS_COLORS: Record<string, string> = {
  todo: 'bg-gray-600 text-gray-200',
  in_progress: 'bg-blue-600 text-blue-100',
  done: 'bg-green-600 text-green-100',
}
const STATUS_LABELS: Record<string, string> = {
  todo: '未着手',
  in_progress: '進行中',
  done: '完了',
}

export function DashboardPage() {
  const [view, setView] = useState<ViewMode>('member')
  const { activeProjectId } = useProjectStore()

  const { data, isLoading, isError, error } = useQuery<DashboardResponse>({
    queryKey: ['dashboard', activeProjectId],
    queryFn: async () => {
      if (!activeProjectId) return { tasks: [], private_counts: {} }
      const res = await api.get('/dashboard', { params: { project_id: activeProjectId } })
      return res.data
    },
    enabled: !!activeProjectId,
    retry: false,
  })

  const tasks = data?.tasks ?? []
  const privateCounts = data?.private_counts ?? {}

  // BUG-023: 404 / サーバーエラーを画面で区別して伝える
  const errDetail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  let errTitle = 'ダッシュボードを表示できません'
  let errBody = '時間をおいて再度お試しください。問題が続く場合は管理者にお問い合わせください。'
  if (errDetail === 'Project has no members') {
    errTitle = 'このプロジェクトにはメンバーがいません'
    errBody =
      'このプロジェクトにはメンバーが割り当てられていないため、タスクを表示できません。管理者に「管理設定 › プロジェクト管理」からメンバーの割当を依頼してください。'
  } else if (errDetail === 'Project not found') {
    errTitle = 'プロジェクトが見つかりません'
    errBody = '選択中のプロジェクトが存在しません。別のプロジェクトを選択してください。'
  }

  const today = new Date().toLocaleDateString('ja-JP', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'short' })
  const totalTasks = tasks.length
  const doneTasks = tasks.filter((t) => t.status === 'done').length
  const inProgressTasks = tasks.filter((t) => t.status === 'in_progress').length
  const todoTasks = tasks.filter((t) => t.status === 'todo').length

  const byUser = tasks.reduce<Record<string, { name: string; tasks: DashboardTask[] }>>((acc, t) => {
    if (!acc[t.user_id]) acc[t.user_id] = { name: t.user_name, tasks: [] }
    acc[t.user_id].tasks.push(t)
    return acc
  }, {})

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">チームダッシュボード</h1>
          <p className="text-gray-700 dark:text-gray-400 text-sm mt-1">{today}</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex rounded-lg overflow-hidden border border-[var(--border)]">
            <button
              onClick={() => setView('member')}
              className={`px-3 py-1.5 text-sm transition-colors ${view === 'member' ? 'bg-indigo-600 text-white' : 'text-gray-700 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'}`}
            >
              メンバー別
            </button>
            <button
              onClick={() => setView('kanban')}
              className={`px-3 py-1.5 text-sm transition-colors ${view === 'kanban' ? 'bg-indigo-600 text-white' : 'text-gray-700 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'}`}
            >
              カンバン
            </button>
          </div>
          <ThemeToggle />
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: '本日のタスク', value: totalTasks, color: 'text-[var(--text-primary)]' },
          { label: '完了', value: doneTasks, color: 'text-green-500 dark:text-green-400' },
          { label: '進行中', value: inProgressTasks, color: 'text-blue-500 dark:text-blue-400' },
          { label: '未着手', value: todoTasks, color: 'text-gray-600 dark:text-gray-400' },
        ].map((c) => (
          <div key={c.label} className="bg-[var(--bg-surface)] rounded-xl p-4 border border-[var(--border)]">
            <p className="text-gray-700 dark:text-gray-400 text-xs mb-1">{c.label}</p>
            <p className={`text-3xl font-bold ${c.color}`}>{c.value}</p>
          </div>
        ))}
      </div>

      {isLoading ? (
        <div className="text-gray-700 dark:text-gray-400 text-center py-16">読み込み中...</div>
      ) : !activeProjectId ? (
        <div className="text-gray-700 dark:text-gray-400 text-center py-16">プロジェクトを選択してください</div>
      ) : isError ? (
        <div className="max-w-xl mx-auto my-12 rounded-xl border border-yellow-500/40 bg-yellow-900/10 p-6 text-center">
          <p className="text-yellow-600 dark:text-yellow-300 font-semibold mb-2">{errTitle}</p>
          <p className="text-gray-700 dark:text-gray-400 text-sm">{errBody}</p>
        </div>
      ) : view === 'member' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {Object.entries(byUser).map(([userId, { name, tasks: memberTasks }]) => {
            const done = memberTasks.filter((t) => t.status === 'done').length
            const pct = memberTasks.length > 0 ? Math.round((done / memberTasks.length) * 100) : 0
            const privateTasks = privateCounts[userId] ?? 0
            return (
              <div key={userId} className="bg-[var(--bg-surface)] rounded-xl p-4 border border-[var(--border)]">
                <div className="flex items-center gap-3 mb-3">
                  <div className="w-9 h-9 rounded-full bg-indigo-600 flex items-center justify-center text-white font-semibold">
                    {name[0]}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-[var(--text-primary)] font-medium text-sm truncate">{name}</p>
                    <p className="text-gray-700 dark:text-gray-400 text-xs">{done}/{memberTasks.length} 完了</p>
                  </div>
                  <span className="text-indigo-500 dark:text-indigo-400 text-sm font-semibold">{pct}%</span>
                </div>
                <div className="w-full bg-[var(--bg-hover)] rounded-full h-1.5 mb-3">
                  <div className="bg-indigo-500 h-1.5 rounded-full transition-all" style={{ width: `${pct}%` }} />
                </div>
                <div className="space-y-1.5">
                  {memberTasks.map((t) => (
                    <div key={t.id} className="flex items-center gap-2 py-1">
                      <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${STATUS_COLORS[t.status]}`}>
                        {STATUS_LABELS[t.status]}
                      </span>
                      <span className="text-[var(--text-primary)] text-sm flex-1 truncate">{t.name}</span>
                      {t.estimated_hours && (
                        <span className="text-gray-600 dark:text-gray-500 text-xs shrink-0">{t.estimated_hours}h</span>
                      )}
                    </div>
                  ))}
                  {privateTasks > 0 && (
                    <p className="text-gray-600 dark:text-gray-500 text-xs">🔒 非表示 {privateTasks}件</p>
                  )}
                </div>
              </div>
            )
          })}
          {Object.keys(byUser).length === 0 && (
            <div className="col-span-3 text-gray-700 dark:text-gray-400 text-center py-16">
              本日のタスクはありません
            </div>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {(['todo', 'in_progress', 'done'] as const).map((status) => (
            <div key={status} className="bg-[var(--bg-surface)] rounded-xl p-4 border border-[var(--border)]">
              <div className="flex items-center gap-2 mb-3">
                <h3 className="text-[var(--text-primary)] font-medium">{STATUS_LABELS[status]}</h3>
                <span className="text-xs bg-[var(--bg-hover)] text-gray-700 dark:text-gray-400 px-2 py-0.5 rounded-full">
                  {tasks.filter((t) => t.status === status).length}
                </span>
              </div>
              <div className="space-y-2">
                {tasks.filter((t) => t.status === status).map((t) => (
                  <div key={t.id} className="bg-[var(--bg-base)] rounded-lg p-3 border border-[var(--border-subtle)]">
                    <p className="text-[var(--text-primary)] text-sm mb-2">{t.name}</p>
                    <div className="flex items-center justify-between">
                      <span
                        className="text-xs px-2 py-0.5 rounded-full"
                        style={{ backgroundColor: t.project_color + '66', color: t.project_color }}
                      >
                        {t.project_name}
                      </span>
                      <div className="flex items-center gap-1.5">
                        <div className="w-5 h-5 rounded-full bg-indigo-600 flex items-center justify-center text-white text-xs">
                          {t.user_name[0]}
                        </div>
                        {t.estimated_hours && (
                          <span className="text-gray-600 dark:text-gray-500 text-xs">{t.estimated_hours}h</span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
