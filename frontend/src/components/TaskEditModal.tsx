import { useState } from 'react'
import type { Task } from '../lib/types'

interface TaskEditModalProps {
  task: Task
  onClose: () => void
  onSave: (data: { name: string; estimated_hours: number | null; is_private: boolean }) => void
  isSaving?: boolean
  errorMessage?: string
}

// タスクの 名称 / 予定時間 / 非表示 を編集するモーダル（T-010）。
// 既存 PATCH /tasks/{id} を利用するため、これ以外のフィールド（所属プロジェクト・業務日付）は編集しない。
export function TaskEditModal({ task, onClose, onSave, isSaving, errorMessage }: TaskEditModalProps) {
  const [name, setName] = useState(task.name)
  const [hours, setHours] = useState(task.estimated_hours != null ? String(task.estimated_hours) : '')
  const [isPrivate, setIsPrivate] = useState(task.is_private)

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) return
    onSave({
      name: name.trim(),
      estimated_hours: hours ? parseFloat(hours) : null,
      is_private: isPrivate,
    })
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div
        className="bg-[var(--bg-surface)] rounded-2xl p-6 border border-[var(--border)] w-full max-w-md"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-[var(--text-primary)] text-lg font-bold mb-4">タスクを編集</h3>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-gray-700 dark:text-gray-400 text-xs mb-1">タスク名</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
              className="w-full px-3 py-2 rounded-lg bg-[var(--bg-input)] border border-[var(--border)] text-[var(--text-primary)] text-sm focus:outline-none focus:border-indigo-500"
            />
          </div>
          <div>
            <label className="block text-gray-700 dark:text-gray-400 text-xs mb-1">予定時間 (h)</label>
            <input
              value={hours}
              onChange={(e) => setHours(e.target.value)}
              type="number"
              step="0.5"
              min="0"
              placeholder="未設定"
              className="w-full px-3 py-2 rounded-lg bg-[var(--bg-input)] border border-[var(--border)] text-[var(--text-primary)] text-sm focus:outline-none focus:border-indigo-500"
            />
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <span className="text-gray-700 dark:text-gray-400 text-sm">非表示</span>
            <div
              onClick={() => setIsPrivate((v) => !v)}
              className={`w-10 h-5 rounded-full transition-colors cursor-pointer ${isPrivate ? 'bg-indigo-600' : 'bg-[var(--bg-hover)]'}`}
            >
              <div className={`w-4 h-4 rounded-full bg-white m-0.5 transition-transform ${isPrivate ? 'translate-x-5' : ''}`} />
            </div>
          </label>
          {errorMessage && <p className="text-sm text-red-400">{errorMessage}</p>}
          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg border border-[var(--border)] text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white text-sm"
            >
              キャンセル
            </button>
            <button
              type="submit"
              disabled={!name.trim() || isSaving}
              className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium transition-colors"
            >
              {isSaving ? '保存中...' : '保存'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
