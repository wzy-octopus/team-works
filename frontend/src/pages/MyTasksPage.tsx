import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { useProjectStore } from '../stores/projectStore'
import { useAuthStore } from '../stores/authStore'
import { jstToday, jstThisMonday, addDays, mondayOf } from '../lib/date'
import { ThemeToggle } from '../components/ThemeToggle'
import { TaskEditModal } from '../components/TaskEditModal'
import { DateNavigator } from '../components/DateNavigator'
import type { Task, TaskStatus } from '../lib/types'

const STATUS_LABELS: Record<TaskStatus, string> = { todo: '未着手', in_progress: '進行中', done: '完了' }
const STATUS_COLORS: Record<TaskStatus, string> = {
  todo: 'bg-gray-600 text-gray-200',
  in_progress: 'bg-blue-600 text-blue-100',
  done: 'bg-green-600 text-green-100',
}
const STATUS_CYCLE: Record<TaskStatus, TaskStatus> = { todo: 'in_progress', in_progress: 'done', done: 'todo' }

function weekdayLabel(dateStr: string): string {
  return new Date(`${dateStr}T12:00:00+09:00`).toLocaleDateString('ja-JP', { weekday: 'short' })
}

export function MyTasksPage() {
  const qc = useQueryClient()
  const { projects } = useProjectStore()
  const { user } = useAuthStore()
  const [filter, setFilter] = useState<TaskStatus | 'all'>('all')
  const [newName, setNewName] = useState('')
  const [newHours, setNewHours] = useState('')
  // null = ユーザー未選択（既定で所属プロジェクトの先頭を選ぶ）。'' = 明示的に「プロジェクトなし」。
  const [newProjectId, setNewProjectId] = useState<string | null>(null)
  const [newPrivate, setNewPrivate] = useState(false)
  const [editing, setEditing] = useState<Task | null>(null)

  // 業務日付は JST 基準（BUG-022）。マイタスクは週単一ビュー：週内の 1 日を選んでその明細を表示する。
  const today = jstToday()
  const thisMonday = jstThisMonday()
  const [weekStart, setWeekStart] = useState(thisMonday)
  // 週内で選択中の日（下部にその日のタスク明細を表示する）。
  const [weekSelectedDay, setWeekSelectedDay] = useState(today)
  const weekEnd = addDays(weekStart, 6)
  const weekDates = Array.from({ length: 7 }, (_, i) => addDays(weekStart, i))

  // 週を移動したときの既定選択日：その週に今日が含まれれば今日、なければ週頭（月曜）。
  function defaultDayForWeek(ws: string): string {
    const we = addDays(ws, 6)
    return today >= ws && today <= we ? today : ws
  }
  // 週ナビ（週の移動＋選択日リセット）。
  function goWeek(newWeekStart: string) {
    setWeekStart(newWeekStart)
    setWeekSelectedDay(defaultDayForWeek(newWeekStart))
  }
  // 任意の日付へジャンプ（その日を含む週に移動してその日を選択）。
  function jumpToDate(d: string) {
    setWeekStart(mondayOf(d))
    setWeekSelectedDay(d)
  }

  // 作成先プロジェクトは自分が所属するもののみに制限する（BUG-021）。
  const myProjects = projects.filter((p) => user?.project_ids?.includes(p.id))
  // 未選択なら所属プロジェクトの先頭を既定にする（読込前は空＝プロジェクトなし）。
  const effectiveProjectId = newProjectId ?? myProjects[0]?.id ?? ''

  const { data: weekTasks = [] } = useQuery<Task[]>({
    queryKey: ['tasks', 'week', weekStart],
    queryFn: async () => {
      const res = await api.get('/tasks', { params: { week_start: weekStart } })
      return res.data.tasks
    },
  })

  // 選択中の日のタスクだけを下部に表示する（7天条は週全体の件数を出す）。
  const activeDate = weekSelectedDay
  const tasks = weekTasks.filter((t) => t.task_date === weekSelectedDay)

  // タスク変更時はマイタスク一覧（日/週）とチームダッシュボードを再取得する
  // （BUG-025・同一ブラウザ内 cache 同期。['tasks'] は日/週の両キーに prefix match する）
  const invalidateTaskViews = () => {
    qc.invalidateQueries({ queryKey: ['tasks'] })
    qc.invalidateQueries({ queryKey: ['dashboard'] })
  }

  const addTask = useMutation({
    mutationFn: (data: object) => api.post('/tasks', data),
    onSuccess: invalidateTaskViews,
  })

  const updateTask = useMutation({
    mutationFn: ({ id, ...data }: {
      id: string
      status?: TaskStatus
      is_private?: boolean
      name?: string
      estimated_hours?: number | null
    }) => api.patch(`/tasks/${id}`, data),
    onSuccess: invalidateTaskViews,
  })

  const deleteTask = useMutation({
    mutationFn: (id: string) => api.delete(`/tasks/${id}`),
    onSuccess: invalidateTaskViews,
  })

  function handleAdd(e: React.FormEvent) {
    e.preventDefault()
    if (!newName.trim()) return
    addTask.mutate({
      name: newName,
      estimated_hours: newHours ? parseFloat(newHours) : null,
      project_id: effectiveProjectId || null,
      is_private: newPrivate,
      task_date: activeDate,
      status: 'todo',
    })
    setNewName('')
    setNewHours('')
    setNewPrivate(false)
  }

  const filtered = filter === 'all' ? tasks : tasks.filter((t) => t.status === filter)
  const doneTasks = tasks.filter((t) => t.status === 'done').length
  const privateTasks = tasks.filter((t) => t.is_private).length
  const totalHours = tasks.reduce((s, t) => s + (t.estimated_hours ?? 0), 0)

  const summaryLabel = activeDate === today ? '本日のタスク' : `${activeDate} のタスク`

  function renderTask(task: Task) {
    const project = projects.find((p) => p.id === task.project_id)
    return (
      <div
        key={task.id}
        className="bg-[var(--bg-surface)] rounded-lg px-4 py-3 border border-[var(--border)] flex items-center gap-3 group"
      >
        <button
          onClick={() => updateTask.mutate({ id: task.id, status: STATUS_CYCLE[task.status] })}
          className={`w-6 h-6 rounded-full border-2 shrink-0 flex items-center justify-center transition-colors ${
            task.status === 'done'
              ? 'bg-green-500 border-green-500 text-white'
              : task.status === 'in_progress'
                ? 'border-blue-500 text-blue-500'
                : 'border-gray-500'
          }`}
        >
          {task.status === 'done' && '✓'}
          {task.status === 'in_progress' && '▶'}
        </button>
        <span className={`flex-1 min-w-0 truncate text-sm ${task.status === 'done' ? 'line-through text-gray-500' : 'text-[var(--text-primary)]'}`}>
          {task.name}
        </span>
        {project && (
          <span
            className="text-xs px-2 py-0.5 rounded-full"
            style={{ backgroundColor: project.color + '33', color: project.color }}
          >
            {project.name}
          </span>
        )}
        {task.is_private && <span className="text-gray-600 dark:text-gray-500 text-xs">🔒</span>}
        {task.estimated_hours && (
          <span className="text-gray-600 dark:text-gray-500 text-xs">{task.estimated_hours}h</span>
        )}
        <span className={`text-xs px-2 py-0.5 rounded ${STATUS_COLORS[task.status]}`}>
          {STATUS_LABELS[task.status]}
        </span>
        <button
          onClick={() => setEditing(task)}
          title="編集"
          className="text-gray-600 hover:text-indigo-400 text-sm opacity-0 group-hover:opacity-100 transition-all"
        >
          ✎
        </button>
        <button
          onClick={() => deleteTask.mutate(task.id)}
          title="削除"
          className="text-gray-600 hover:text-red-400 text-sm opacity-0 group-hover:opacity-100 transition-all"
        >
          ✕
        </button>
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">マイタスク</h1>
        <div className="flex items-center gap-3 flex-wrap">
          {/* 日付ジャンプ（任意の日付へ移動してその日を選択） */}
          <DateNavigator
            value={weekSelectedDay}
            max={today}
            onChange={jumpToDate}
          />
          {weekSelectedDay !== today && (
            <button
              onClick={() => jumpToDate(today)}
              className="px-3 py-1.5 rounded-lg border border-[var(--border)] text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white text-sm"
            >
              今日
            </button>
          )}

          {/* 週ナビ（前後の週へ移動） */}
          <div className="flex items-center gap-1 rounded-lg border border-[var(--border)] px-1">
            <button
              onClick={() => goWeek(addDays(weekStart, -7))}
              className="px-2 py-1 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            >
              ‹
            </button>
            <span className="text-[var(--text-primary)] text-sm px-1 whitespace-nowrap">
              {weekStart} 〜 {weekEnd}
            </span>
            <button
              onClick={() => goWeek(addDays(weekStart, 7))}
              disabled={weekStart >= thisMonday}
              className="px-2 py-1 text-[var(--text-muted)] hover:text-[var(--text-primary)] disabled:opacity-30 disabled:cursor-not-allowed"
            >
              ›
            </button>
          </div>
          <ThemeToggle />
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: summaryLabel, value: tasks.length, color: 'text-[var(--text-primary)]' },
          { label: '完了', value: doneTasks, color: 'text-green-500 dark:text-green-400' },
          { label: '予定時間', value: `${totalHours}h`, color: 'text-indigo-500 dark:text-indigo-400' },
          { label: '非表示', value: privateTasks, color: 'text-gray-600 dark:text-gray-400' },
        ].map((c) => (
          <div key={c.label} className="bg-[var(--bg-surface)] rounded-xl p-4 border border-[var(--border)]">
            <p className="text-gray-700 dark:text-gray-400 text-xs mb-1">{c.label}</p>
            <p className={`text-3xl font-bold ${c.color}`}>{c.value}</p>
          </div>
        ))}
      </div>

      {/* 7天条（各日の件数・今日/選択日をハイライト。クリックでその日の明細を下部に表示） */}
      <div className="flex gap-2 mb-6 overflow-x-auto">
        {weekDates.map((d) => {
          const count = weekTasks.filter((t) => t.task_date === d).length
          const isSelected = d === weekSelectedDay
          const isToday = d === today
          return (
            <button
              key={d}
              onClick={() => setWeekSelectedDay(d)}
              className={`flex-1 min-w-[4.5rem] rounded-xl border px-2 py-2 text-center transition-colors ${
                isSelected
                  ? 'border-indigo-500 ring-1 ring-indigo-500 bg-[var(--bg-surface)]'
                  : 'border-[var(--border)] hover:bg-[var(--bg-hover)]'
              }`}
            >
              <div className={`text-xs ${isToday ? 'text-indigo-500 dark:text-indigo-400 font-semibold' : 'text-gray-600 dark:text-gray-400'}`}>
                {weekdayLabel(d)} {d.slice(5)}
              </div>
              <div className="text-lg font-bold text-[var(--text-primary)]">{count}</div>
            </button>
          )
        })}
      </div>

      {/* Add form（選択中の日＝7天条/日付ジャンプで選んだ日に追加） */}
      <form onSubmit={handleAdd} className="bg-[var(--bg-surface)] rounded-xl p-4 border border-[var(--border)] mb-6">
          <div className="flex gap-3 flex-wrap">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="タスク名を入力..."
              className="flex-1 min-w-48 px-3 py-2 rounded-lg bg-[var(--bg-input)] border border-[var(--border)] text-[var(--text-primary)] placeholder-gray-500 text-sm focus:outline-none focus:border-indigo-500"
            />
            <input
              value={newHours}
              onChange={(e) => setNewHours(e.target.value)}
              placeholder="予定時間 (h)"
              type="number"
              step="0.5"
              min="0"
              className="w-32 px-3 py-2 rounded-lg bg-[var(--bg-input)] border border-[var(--border)] text-[var(--text-primary)] placeholder-gray-500 text-sm focus:outline-none focus:border-indigo-500"
            />
            <select
              value={effectiveProjectId}
              onChange={(e) => setNewProjectId(e.target.value)}
              className="w-44 px-3 py-2 rounded-lg bg-[var(--bg-input)] border border-[var(--border)] text-gray-900 dark:text-white text-sm focus:outline-none focus:border-indigo-500"
            >
              <option value="" className="bg-[var(--bg-surface)]">（プロジェクトなし）</option>
              {myProjects.map((p) => (
                <option key={p.id} value={p.id} className="bg-[var(--bg-surface)]">{p.name}</option>
              ))}
            </select>
            <label className="flex items-center gap-2 cursor-pointer">
              <span className="text-gray-700 dark:text-gray-400 text-sm">非表示</span>
              <div
                onClick={() => setNewPrivate((v) => !v)}
                className={`w-10 h-5 rounded-full transition-colors cursor-pointer ${newPrivate ? 'bg-indigo-600' : 'bg-[var(--bg-hover)]'}`}
              >
                <div className={`w-4 h-4 rounded-full bg-white m-0.5 transition-transform ${newPrivate ? 'translate-x-5' : ''}`} />
              </div>
            </label>
            <button
              type="submit"
              className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors"
            >
              追加
            </button>
          </div>
          {effectiveProjectId === '' && (
            <p className="mt-3 text-xs text-gray-600 dark:text-gray-400">
              個人タスクとして作成されます（チームダッシュボードには表示されません）
            </p>
          )}
          {addTask.isError && (
            <p className="mt-3 text-sm text-red-400">
              {(addTask.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
                'タスクの作成に失敗しました'}
            </p>
          )}
      </form>

      {/* Filter */}
      <div className="flex items-center gap-2 mb-4">
        {(['all', 'todo', 'in_progress', 'done'] as const).map((s) => {
          const count = s === 'all' ? tasks.length : tasks.filter((t) => t.status === s).length
          return (
            <button
              key={s}
              onClick={() => setFilter(s)}
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors flex items-center gap-1.5 ${
                filter === s ? 'bg-indigo-600 text-white' : 'text-gray-700 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
              }`}
            >
              {s === 'all' ? 'すべて' : STATUS_LABELS[s]}
              <span className="text-xs bg-[var(--bg-hover)] px-1.5 py-0.5 rounded-full">{count}</span>
            </button>
          )
        })}
        <div className="flex-1" />
        <div className="text-sm text-gray-700 dark:text-gray-400">{doneTasks} / {tasks.length} 完了</div>
      </div>

      {/* Progress bar */}
      {tasks.length > 0 && (
        <div className="w-full bg-[var(--bg-hover)] rounded-full h-1.5 mb-4">
          <div
            className="bg-indigo-500 h-1.5 rounded-full transition-all"
            style={{ width: `${Math.round((doneTasks / tasks.length) * 100)}%` }}
          />
        </div>
      )}

      {/* タスク一覧（選択中の日。週モードでは 7天条で選んだ日） */}
      <div className="space-y-2">
        {filtered.length === 0 ? (
          <div className="text-gray-700 dark:text-gray-400 text-center py-12">タスクがありません</div>
        ) : (
          filtered.map((task) => renderTask(task))
        )}
      </div>

      {editing && (
        <TaskEditModal
          task={editing}
          isSaving={updateTask.isPending}
          errorMessage={
            updateTask.isError
              ? ((updateTask.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
                'タスクの更新に失敗しました')
              : undefined
          }
          onClose={() => setEditing(null)}
          onSave={(data) =>
            updateTask.mutate(
              { id: editing.id, ...data },
              { onSuccess: () => setEditing(null) },
            )
          }
        />
      )}
    </div>
  )
}
