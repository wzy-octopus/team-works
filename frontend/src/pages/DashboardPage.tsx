import { useState, Fragment } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { useProjectStore } from '../stores/projectStore'
import { jstToday, jstThisMonday, addDays } from '../lib/date'
import { ThemeToggle } from '../components/ThemeToggle'
import type { DashboardTask, PastIncompleteSummary, DashboardWeek } from '../lib/types'

type ViewMode = 'member' | 'kanban'
type Granularity = 'day' | 'week'

type DashboardResponse = {
  tasks: DashboardTask[]
  private_counts: Record<string, number>
  past_incomplete_summary: PastIncompleteSummary
}

const INCOMPLETE_SUMMARY_PAGE_SIZE = 10

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
const KANBAN_STATUSES = ['todo', 'in_progress', 'done'] as const

function weekdayLabel(dateStr: string): string {
  return new Date(`${dateStr}T12:00:00+09:00`).toLocaleDateString('ja-JP', { weekday: 'short' })
}

export function DashboardPage() {
  const [view, setView] = useState<ViewMode>('member')
  const [summaryPage, setSummaryPage] = useState(0)
  const [isIncompleteSummaryOpen, setIsIncompleteSummaryOpen] = useState(false)
  // 週モード member別: クリックで展開中のメンバー（その人の1週間のタスク明細を表示）
  const [expandedUser, setExpandedUser] = useState<string | null>(null)
  // 週モード カンバン: クリックで展開中の状態（その状態の1週間のタスク明細を表示）
  const [expandedStatus, setExpandedStatus] = useState<string | null>(null)
  const businessToday = jstToday()
  const thisMonday = jstThisMonday()
  const [granularity, setGranularity] = useState<Granularity>('day')
  const [selectedDate, setSelectedDate] = useState(businessToday)
  const [weekStart, setWeekStart] = useState(thisMonday)
  const weekEnd = addDays(weekStart, 6)
  const { activeProjectId } = useProjectStore()

  const dayQuery = useQuery<DashboardResponse>({
    queryKey: ['dashboard', activeProjectId, selectedDate],
    queryFn: async () => {
      const res = await api.get('/dashboard', {
        params: { project_id: activeProjectId, task_date: selectedDate },
      })
      return res.data
    },
    enabled: !!activeProjectId && granularity === 'day',
    retry: false,
  })

  const weekQuery = useQuery<DashboardWeek>({
    queryKey: ['dashboard', 'week', activeProjectId, weekStart],
    queryFn: async () => {
      const res = await api.get('/dashboard/week', {
        params: { project_id: activeProjectId, week_start: weekStart },
      })
      return res.data
    },
    enabled: !!activeProjectId && granularity === 'week',
    retry: false,
  })

  const activeQuery = granularity === 'day' ? dayQuery : weekQuery
  const isLoading = activeQuery.isLoading
  const isError = activeQuery.isError
  const error = activeQuery.error

  // --- 日モードのデータ ---
  const tasks = dayQuery.data?.tasks ?? []
  const privateCounts = dayQuery.data?.private_counts ?? {}
  const pastIncompleteSummary = dayQuery.data?.past_incomplete_summary ?? { total: 0, items: [] }
  const summaryTotalPages = Math.max(
    1,
    Math.ceil(pastIncompleteSummary.items.length / INCOMPLETE_SUMMARY_PAGE_SIZE),
  )
  const currentSummaryPage = Math.min(summaryPage, summaryTotalPages - 1)
  const summaryPageItems = pastIncompleteSummary.items.slice(
    currentSummaryPage * INCOMPLETE_SUMMARY_PAGE_SIZE,
    (currentSummaryPage + 1) * INCOMPLETE_SUMMARY_PAGE_SIZE,
  )

  // --- 週モードのデータ ---
  const weekDays = weekQuery.data?.days ?? []
  const weekMembers = weekQuery.data?.members ?? []
  const weekTasks = weekQuery.data?.tasks ?? []
  // 看板の週グリッド用: 日ごとに全メンバーの status を合算する。
  const weekDayTotals = weekDays.map((d, i) => {
    const acc = { date: d, todo: 0, in_progress: 0, done: 0, private_count: 0 }
    for (const m of weekMembers) {
      const e = m.days[i]
      if (!e) continue
      acc.todo += e.todo
      acc.in_progress += e.in_progress
      acc.done += e.done
      acc.private_count += e.private_count
    }
    return acc
  })

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
  } else if (errDetail === 'You are not a member of this project') {
    errTitle = 'このプロジェクトを表示する権限がありません'
    errBody = 'あなたはこのプロジェクトのメンバーではありません。管理者にプロジェクトへの追加を依頼してください。'
  }

  const selectedDateLabel = new Date(`${selectedDate}T12:00:00+09:00`).toLocaleDateString('ja-JP', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'short',
  })

  // サマリカードの値（日=単日 / 週=週合計）
  const dayTotal = tasks.length
  const dayDone = tasks.filter((t) => t.status === 'done').length
  const dayInProgress = tasks.filter((t) => t.status === 'in_progress').length
  const dayTodo = tasks.filter((t) => t.status === 'todo').length
  const weekTodo = weekDayTotals.reduce((s, d) => s + d.todo, 0)
  const weekInProgress = weekDayTotals.reduce((s, d) => s + d.in_progress, 0)
  const weekDone = weekDayTotals.reduce((s, d) => s + d.done, 0)
  const summaryCards =
    granularity === 'week'
      ? [
          { label: '今週のタスク', value: weekTodo + weekInProgress + weekDone, color: 'text-[var(--text-primary)]' },
          { label: '完了', value: weekDone, color: 'text-green-500 dark:text-green-400' },
          { label: '進行中', value: weekInProgress, color: 'text-blue-500 dark:text-blue-400' },
          { label: '未着手', value: weekTodo, color: 'text-gray-600 dark:text-gray-400' },
        ]
      : [
          {
            label: selectedDate === businessToday ? '本日のタスク' : `${selectedDate} のタスク`,
            value: dayTotal,
            color: 'text-[var(--text-primary)]',
          },
          { label: '完了', value: dayDone, color: 'text-green-500 dark:text-green-400' },
          { label: '進行中', value: dayInProgress, color: 'text-blue-500 dark:text-blue-400' },
          { label: '未着手', value: dayTodo, color: 'text-gray-600 dark:text-gray-400' },
        ]

  const byUser = tasks.reduce<Record<string, { name: string; tasks: DashboardTask[] }>>((acc, t) => {
    if (!acc[t.user_id]) acc[t.user_id] = { name: t.user_name, tasks: [] }
    acc[t.user_id].tasks.push(t)
    return acc
  }, {})

  const dayControlActive = granularity === 'day'
  const weekControlActive = granularity === 'week'

  // 週グリッドの日ヘッダ／セルをクリックしてその日にドリルダウンする。
  function goDay(date: string) {
    setSelectedDate(date)
    setGranularity('day')
  }

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">チームダッシュボード</h1>
          <p className="text-gray-700 dark:text-gray-400 text-sm mt-1">
            {granularity === 'week' ? `${weekStart} 〜 ${weekEnd}` : selectedDateLabel}
          </p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          {/* 日入力（並列常駐・クリックで日モード） */}
          <div className={`flex items-center gap-2 rounded-lg px-1 ${dayControlActive ? 'ring-1 ring-indigo-500' : ''}`}>
            <input
              type="date"
              value={selectedDate}
              max={businessToday}
              onFocus={() => setGranularity('day')}
              onChange={(e) => goDay(e.target.value || businessToday)}
              className="px-3 py-1.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border)] text-[var(--text-primary)] text-sm focus:outline-none focus:border-indigo-500"
            />
            {dayControlActive && selectedDate !== businessToday && (
              <button
                onClick={() => goDay(businessToday)}
                className="px-3 py-1.5 rounded-lg border border-[var(--border)] text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white text-sm"
              >
                今日
              </button>
            )}
          </div>

          {/* 週ナビ（並列常駐・クリックで週モード） */}
          <div className={`flex items-center gap-1 rounded-lg border border-[var(--border)] px-1 ${weekControlActive ? 'ring-1 ring-indigo-500' : ''}`}>
            <button
              onClick={() => {
                setWeekStart(addDays(weekStart, -7))
                setGranularity('week')
              }}
              className="px-2 py-1 text-[var(--text-muted)] hover:text-[var(--text-primary)]"
            >
              ‹
            </button>
            <button
              onClick={() => setGranularity('week')}
              className="text-[var(--text-primary)] text-sm px-1 whitespace-nowrap"
            >
              {weekStart} 〜 {weekEnd}
            </button>
            <button
              onClick={() => {
                setWeekStart(addDays(weekStart, 7))
                setGranularity('week')
              }}
              disabled={weekStart >= thisMonday}
              className="px-2 py-1 text-[var(--text-muted)] hover:text-[var(--text-primary)] disabled:opacity-30 disabled:cursor-not-allowed"
            >
              ›
            </button>
          </div>

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
        {summaryCards.map((c) => (
          <div key={c.label} className="bg-[var(--bg-surface)] rounded-xl p-4 border border-[var(--border)]">
            <p className="text-gray-700 dark:text-gray-400 text-xs mb-1">{c.label}</p>
            <p className={`text-3xl font-bold ${c.color}`}>{c.value}</p>
          </div>
        ))}
      </div>

      {/* 昨日以前の未完了タスク（日モード・カンバンのみ。週モードはグリッドが代替） */}
      {granularity === 'day' && view === 'kanban' && activeProjectId && !isLoading && !isError && (
        <div className="bg-[var(--bg-surface)] rounded-xl p-4 border border-[var(--border)] mb-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-[var(--text-primary)] font-medium">昨日以前の未完了タスク</h2>
              <p className="text-gray-700 dark:text-gray-400 text-xs mt-1">昨日から過去30日</p>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm font-semibold text-indigo-500 dark:text-indigo-400 whitespace-nowrap">
                total {pastIncompleteSummary.total}件
              </span>
              <button
                onClick={() => setIsIncompleteSummaryOpen((value) => !value)}
                className="px-3 py-1.5 rounded-lg border border-[var(--border)] text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white text-sm transition-colors"
              >
                {isIncompleteSummaryOpen ? '閉じる' : '詳細'}
              </button>
            </div>
          </div>
          <div
            className={`grid transition-all duration-200 ease-out ${
              isIncompleteSummaryOpen ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'
            }`}
          >
            <div className="overflow-hidden">
              <div className="divide-y divide-[var(--border-subtle)] mt-3">
                {summaryPageItems.map((item) => (
                  <button
                    key={item.task_date}
                    onClick={() => goDay(item.task_date)}
                    className="w-full flex items-center justify-between py-2 hover:bg-[var(--bg-hover)] rounded px-1"
                  >
                    <span className="text-sm text-[var(--text-primary)]">{item.task_date}</span>
                    <span className="text-sm text-gray-700 dark:text-gray-300">{item.count}件</span>
                  </button>
                ))}
              </div>
              <div className="flex items-center justify-end gap-3 pt-3">
                <button
                  onClick={() => setSummaryPage((page) => Math.max(0, page - 1))}
                  disabled={currentSummaryPage === 0}
                  className="px-3 py-1.5 rounded-lg border border-[var(--border)] text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white text-sm disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  前へ
                </button>
                <span className="text-sm text-gray-700 dark:text-gray-400">
                  {currentSummaryPage + 1} / {summaryTotalPages}
                </span>
                <button
                  onClick={() => setSummaryPage((page) => Math.min(summaryTotalPages - 1, page + 1))}
                  disabled={currentSummaryPage >= summaryTotalPages - 1}
                  className="px-3 py-1.5 rounded-lg border border-[var(--border)] text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white text-sm disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  次へ
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {isLoading ? (
        <div className="text-gray-700 dark:text-gray-400 text-center py-16">読み込み中...</div>
      ) : !activeProjectId ? (
        <div className="text-gray-700 dark:text-gray-400 text-center py-16">プロジェクトを選択してください</div>
      ) : isError ? (
        <div className="max-w-xl mx-auto my-12 rounded-xl border border-yellow-500/40 bg-yellow-900/10 p-6 text-center">
          <p className="text-yellow-600 dark:text-yellow-300 font-semibold mb-2">{errTitle}</p>
          <p className="text-gray-700 dark:text-gray-400 text-sm">{errBody}</p>
        </div>
      ) : granularity === 'week' ? (
        /* ===== 週モード: 集計グリッド + ドリルダウン ===== */
        view === 'member' ? (
          <div className="bg-[var(--bg-surface)] rounded-xl border border-[var(--border)] overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  <th className="text-left text-gray-700 dark:text-gray-400 font-medium px-3 py-2 sticky left-0 bg-[var(--bg-surface)]">
                    メンバー
                  </th>
                  {weekDays.map((d) => (
                    <th key={d} className="px-2 py-2 text-center">
                      <button
                        onClick={() => goDay(d)}
                        className={`text-xs hover:text-indigo-500 dark:hover:text-indigo-400 ${
                          d === businessToday ? 'text-indigo-500 dark:text-indigo-400 font-semibold' : 'text-gray-700 dark:text-gray-400'
                        }`}
                      >
                        {weekdayLabel(d)}
                        <br />
                        {d.slice(5)}
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {weekMembers.map((m) => {
                  const isExpanded = expandedUser === m.user_id
                  const toggleExpand = () => setExpandedUser(isExpanded ? null : m.user_id)
                  const dayGroups = weekDays
                    .map((d, i) => ({
                      date: d,
                      tasks: weekTasks.filter((t) => t.user_id === m.user_id && t.task_date === d),
                      privateCount: m.days[i]?.private_count ?? 0,
                    }))
                    .filter((g) => g.tasks.length > 0 || g.privateCount > 0)
                  return (
                    <Fragment key={m.user_id}>
                      <tr className="border-b border-[var(--border-subtle)] last:border-0">
                        <td className="px-3 py-2 text-[var(--text-primary)] whitespace-nowrap sticky left-0 bg-[var(--bg-surface)]">
                          <button
                            onClick={toggleExpand}
                            title="クリックでこの人の1週間のタスクを展開"
                            className="flex items-center gap-2 hover:text-indigo-500 dark:hover:text-indigo-400 transition-colors"
                          >
                            <span className="text-gray-400 text-xs w-3 shrink-0">{isExpanded ? '▾' : '▸'}</span>
                            <div className="w-6 h-6 rounded-full bg-indigo-600 flex items-center justify-center text-white text-xs shrink-0">
                              {m.user_name[0]}
                            </div>
                            <span className="truncate max-w-[8rem]">{m.user_name}</span>
                          </button>
                        </td>
                        {m.days.map((e) => {
                          const total = e.todo + e.in_progress + e.done
                          const empty = total === 0 && e.private_count === 0
                          const pct = total > 0 ? Math.round((e.done / total) * 100) : 0
                          return (
                            <td key={e.date} className="px-2 py-2 text-center align-middle">
                              <button
                                onClick={toggleExpand}
                                className="w-full rounded-lg px-1 py-1 hover:bg-[var(--bg-hover)] transition-colors"
                              >
                                {empty ? (
                                  <span className="text-gray-400 dark:text-gray-600">·</span>
                                ) : (
                                  <div className="flex flex-col items-center gap-1">
                                    <span className="text-[var(--text-primary)] text-xs">
                                      {e.done}/{total}
                                    </span>
                                    <div className="w-10 bg-[var(--bg-hover)] rounded-full h-1">
                                      <div className="bg-indigo-500 h-1 rounded-full" style={{ width: `${pct}%` }} />
                                    </div>
                                    {e.private_count > 0 && (
                                      <span className="text-gray-500 text-[10px]">🔒{e.private_count}</span>
                                    )}
                                  </div>
                                )}
                              </button>
                            </td>
                          )
                        })}
                      </tr>
                      <tr className="bg-[var(--bg-base)]">
                        <td colSpan={weekDays.length + 1} className="p-0">
                          <div
                            className={`grid transition-all duration-200 ease-out ${
                              isExpanded ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'
                            }`}
                          >
                            <div className="overflow-hidden">
                              <div className="px-4 py-3">
                                {dayGroups.length === 0 ? (
                                  <p className="text-gray-500 text-xs">この週のタスクはありません</p>
                                ) : (
                                  <div className="space-y-3">
                                    {dayGroups.map((g) => (
                                      <div key={g.date}>
                                        <div className="text-xs text-gray-500 mb-1">
                                          {weekdayLabel(g.date)} {g.date.slice(5)}
                                        </div>
                                        <div className="space-y-1">
                                          {g.tasks.map((t) => (
                                            <div key={t.id} className="flex items-center gap-2">
                                              <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${STATUS_COLORS[t.status]}`}>
                                                {STATUS_LABELS[t.status]}
                                              </span>
                                              <span className={`text-xs ${t.status === 'done' ? 'line-through text-gray-500' : 'text-[var(--text-primary)]'}`}>
                                                {t.name}
                                              </span>
                                              {t.is_private && <span className="text-[10px]">🔒</span>}
                                              {t.estimated_hours != null && (
                                                <span className="text-[10px] text-gray-500">{t.estimated_hours}h</span>
                                              )}
                                            </div>
                                          ))}
                                          {g.privateCount > 0 && (
                                            <p className="text-[10px] text-gray-500">🔒 非表示 {g.privateCount}件</p>
                                          )}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    </Fragment>
                  )
                })}
                {weekMembers.length === 0 && (
                  <tr>
                    <td colSpan={8} className="text-center text-gray-700 dark:text-gray-400 py-12">
                      メンバーがいません
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        ) : (
          /* 看板の週: 状態 × 7日 */
          <div className="bg-[var(--bg-surface)] rounded-xl border border-[var(--border)] overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  <th className="text-left text-gray-700 dark:text-gray-400 font-medium px-3 py-2 sticky left-0 bg-[var(--bg-surface)]">
                    状態
                  </th>
                  {weekDays.map((d) => (
                    <th key={d} className="px-2 py-2 text-center">
                      <button
                        onClick={() => goDay(d)}
                        className={`text-xs hover:text-indigo-500 dark:hover:text-indigo-400 ${
                          d === businessToday ? 'text-indigo-500 dark:text-indigo-400 font-semibold' : 'text-gray-700 dark:text-gray-400'
                        }`}
                      >
                        {weekdayLabel(d)}
                        <br />
                        {d.slice(5)}
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {KANBAN_STATUSES.map((s) => {
                  const isExpanded = expandedStatus === s
                  const toggleExpand = () => setExpandedStatus(isExpanded ? null : s)
                  const dayGroups = weekDays
                    .map((d) => ({
                      date: d,
                      tasks: weekTasks.filter((t) => t.status === s && t.task_date === d),
                    }))
                    .filter((g) => g.tasks.length > 0)
                  return (
                    <Fragment key={s}>
                      <tr className="border-b border-[var(--border-subtle)]">
                        <td className="px-3 py-2 sticky left-0 bg-[var(--bg-surface)]">
                          <button
                            onClick={toggleExpand}
                            title="クリックでこの状態の1週間のタスクを展開"
                            className="flex items-center gap-2 hover:opacity-80 transition-opacity"
                          >
                            <span className="text-gray-400 text-xs w-3 shrink-0">{isExpanded ? '▾' : '▸'}</span>
                            <span className={`text-xs px-2 py-0.5 rounded font-medium ${STATUS_COLORS[s]}`}>
                              {STATUS_LABELS[s]}
                            </span>
                          </button>
                        </td>
                        {weekDayTotals.map((d) => (
                          <td key={d.date} className="px-2 py-2 text-center">
                            <button
                              onClick={toggleExpand}
                              className="w-full rounded-lg py-1 hover:bg-[var(--bg-hover)] transition-colors text-[var(--text-primary)]"
                            >
                              {d[s] > 0 ? d[s] : <span className="text-gray-400 dark:text-gray-600">·</span>}
                            </button>
                          </td>
                        ))}
                      </tr>
                      <tr className="bg-[var(--bg-base)]">
                        <td colSpan={weekDays.length + 1} className="p-0">
                          <div
                            className={`grid transition-all duration-200 ease-out ${
                              isExpanded ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'
                            }`}
                          >
                            <div className="overflow-hidden">
                              <div className="px-4 py-3">
                                {dayGroups.length === 0 ? (
                                  <p className="text-gray-500 text-xs">この状態のタスクはありません</p>
                                ) : (
                                  <div className="space-y-3">
                                    {dayGroups.map((g) => (
                                      <div key={g.date}>
                                        <div className="text-xs text-gray-500 mb-1">
                                          {weekdayLabel(g.date)} {g.date.slice(5)}
                                        </div>
                                        <div className="space-y-1">
                                          {g.tasks.map((t) => (
                                            <div key={t.id} className="flex items-center gap-2">
                                              <div className="w-5 h-5 rounded-full bg-indigo-600 flex items-center justify-center text-white text-[10px] shrink-0">
                                                {t.user_name[0]}
                                              </div>
                                              <span className="text-xs text-gray-600 dark:text-gray-400 shrink-0">{t.user_name}</span>
                                              <span className={`text-xs ${t.status === 'done' ? 'line-through text-gray-500' : 'text-[var(--text-primary)]'}`}>
                                                {t.name}
                                              </span>
                                              {t.is_private && <span className="text-[10px]">🔒</span>}
                                              {t.estimated_hours != null && (
                                                <span className="text-[10px] text-gray-500">{t.estimated_hours}h</span>
                                              )}
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    </Fragment>
                  )
                })}
                <tr>
                  <td className="px-3 py-2 text-gray-600 dark:text-gray-400 text-xs sticky left-0 bg-[var(--bg-surface)]">🔒 非表示</td>
                  {weekDayTotals.map((d) => (
                    <td key={d.date} className="px-2 py-2 text-center text-gray-600 dark:text-gray-400 text-xs">
                      {d.private_count > 0 ? d.private_count : '·'}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        )
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
              {selectedDate === businessToday
                ? '本日のタスクはありません'
                : `${selectedDate} のタスクはありません`}
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
