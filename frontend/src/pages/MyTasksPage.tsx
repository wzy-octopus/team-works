import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { useProjectStore } from '../stores/projectStore'
import { useAuthStore } from '../stores/authStore'
import { jstToday } from '../lib/date'
import { ThemeToggle } from '../components/ThemeToggle'
import type { Task, TaskStatus } from '../lib/types'

const STATUS_LABELS: Record<TaskStatus, string> = { todo: '未着手', in_progress: '進行中', done: '完了' }
const STATUS_COLORS: Record<TaskStatus, string> = {
  todo: 'bg-gray-600 text-gray-200',
  in_progress: 'bg-blue-600 text-blue-100',
  done: 'bg-green-600 text-green-100',
}
const STATUS_CYCLE: Record<TaskStatus, TaskStatus> = { todo: 'in_progress', in_progress: 'done', done: 'todo' }

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

  // 業務日付は JST 基準（BUG-022）。日付ピッカーで過去日も閲覧できる。
  const today = jstToday()
  const [selectedDate, setSelectedDate] = useState(today)

  // 作成先プロジェクトは自分が所属するもののみに制限する（BUG-021）。
  const myProjects = projects.filter((p) => user?.project_ids?.includes(p.id))
  // 未選択なら所属プロジェクトの先頭を既定にする（読込前は空＝プロジェクトなし）。
  const effectiveProjectId = newProjectId ?? myProjects[0]?.id ?? ''

  const { data: tasks = [] } = useQuery<Task[]>({
    queryKey: ['tasks', selectedDate],
    queryFn: async () => {
      const res = await api.get('/tasks', { params: { task_date: selectedDate } })
      return res.data.tasks
    },
  })

  const addTask = useMutation({
    mutationFn: (data: object) => api.post('/tasks', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tasks'] }),
  })

  const updateTask = useMutation({
    mutationFn: ({ id, ...data }: { id: string; status?: TaskStatus; is_private?: boolean; name?: string }) =>
      api.patch(`/tasks/${id}`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tasks'] }),
  })

  const deleteTask = useMutation({
    mutationFn: (id: string) => api.delete(`/tasks/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tasks'] }),
  })

  function handleAdd(e: React.FormEvent) {
    e.preventDefault()
    if (!newName.trim()) return
    addTask.mutate({
      name: newName,
      estimated_hours: newHours ? parseFloat(newHours) : null,
      project_id: effectiveProjectId || null,
      is_private: newPrivate,
      task_date: selectedDate,
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

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">マイタスク</h1>
        <div className="flex items-center gap-3">
          <input
            type="date"
            value={selectedDate}
            max={today}
            onChange={(e) => setSelectedDate(e.target.value || today)}
            className="px-3 py-1.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border)] text-[var(--text-primary)] text-sm focus:outline-none focus:border-indigo-500"
          />
          {selectedDate !== today && (
            <button
              onClick={() => setSelectedDate(today)}
              className="px-3 py-1.5 rounded-lg border border-[var(--border)] text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white text-sm"
            >
              今日
            </button>
          )}
          <ThemeToggle />
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: selectedDate === today ? '本日のタスク' : `${selectedDate} のタスク`, value: tasks.length, color: 'text-[var(--text-primary)]' },
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

      {/* Add form */}
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

      {/* Task list */}
      <div className="space-y-2">
        {filtered.length === 0 ? (
          <div className="text-gray-700 dark:text-gray-400 text-center py-12">タスクがありません</div>
        ) : (
          filtered.map((task) => {
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
                <span className={`flex-1 text-sm ${task.status === 'done' ? 'line-through text-gray-500' : 'text-[var(--text-primary)]'}`}>
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
                  onClick={() => deleteTask.mutate(task.id)}
                  className="text-gray-600 hover:text-red-400 text-sm opacity-0 group-hover:opacity-100 transition-all"
                >
                  ✕
                </button>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
