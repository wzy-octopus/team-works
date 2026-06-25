import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { useAuthStore } from '../stores/authStore'
import { useProjectStore } from '../stores/projectStore'

const navItemClass = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
    isActive
      ? 'bg-indigo-600 text-white'
      : 'text-gray-700 dark:text-gray-300 hover:bg-[var(--bg-hover)] hover:text-gray-900 dark:hover:text-white'
  }`

export function Sidebar() {
  const { user, logout } = useAuthStore()
  const { projects, activeProjectId, setActiveProject } = useProjectStore()
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data: unread } = useQuery<{ count: number }>({
    queryKey: ['weekly-report-unread'],
    queryFn: async () => (await api.get('/weekly-reports/unread-feedback-count')).data,
    refetchOnWindowFocus: true,
  })
  const markRead = useMutation({
    mutationFn: () => api.post('/weekly-reports/feedback/mark-read'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['weekly-report-unread'] }),
  })
  const unreadCount = unread?.count ?? 0

  const [mcpCopied, setMcpCopied] = useState(false)

  function handleLogout() {
    logout()
    qc.clear()
    navigate('/login')
  }

  async function copyMcpConfig() {
    const { data } = await api.post('/auth/mcp-token')
    const config = {
      mcpServers: {
        'TeamWorks': {
          type: 'http',
          url: `${window.location.origin}/mcp`,
          headers: { Authorization: `Bearer ${data.access_token}` },
        },
      },
    }
    await navigator.clipboard.writeText(JSON.stringify(config, null, 2))
    setMcpCopied(true)
    setTimeout(() => setMcpCopied(false), 2000)
  }

  return (
    <aside className="w-56 shrink-0 bg-[var(--bg-surface)] flex flex-col h-screen sticky top-0">
      <div className="p-4 border-b border-[var(--border)]">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-indigo-600 flex items-center justify-center text-white text-xs font-bold">
            T
          </div>
          <span className="text-[var(--text-primary)] font-semibold text-sm">TeamWorks</span>
        </div>
      </div>

      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        <NavLink to="/dashboard" className={navItemClass}>
          <span>📊</span> ダッシュボード
        </NavLink>
        <NavLink to="/my-tasks" className={navItemClass}>
          <span>✅</span> マイタスク
        </NavLink>
        <NavLink
          to="/weekly-report"
          className={navItemClass}
          onClick={() => {
            if (unreadCount > 0) markRead.mutate()
          }}
        >
          <span>📝</span> 週間レポート
          {unreadCount > 0 && (
            <span className="ml-auto inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1.5 rounded-full bg-red-600 text-white text-xs font-semibold">
              {unreadCount}
            </span>
          )}
        </NavLink>
        <NavLink to="/inbox" className={navItemClass}>
          <span>📬</span> 週報受信トレイ
        </NavLink>
        <NavLink to="/admin" className={navItemClass}>
          <span>⚙️</span> 管理設定
        </NavLink>

        {projects.length > 0 && (
          <div className="pt-3">
            <p className="text-xs text-gray-500 px-3 mb-2 uppercase tracking-wider">Projects</p>
            {projects.map((p) => (
              <button
                key={p.id}
                onClick={() => setActiveProject(p.id)}
                className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                  activeProjectId === p.id
                    ? 'text-gray-900 dark:text-white bg-[var(--bg-hover)]'
                    : 'text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white'
                }`}
              >
                <span
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: p.color }}
                />
                <span className="truncate">{p.name}</span>
              </button>
            ))}
          </div>
        )}
      </nav>

      <div className="p-3 border-t border-[var(--border)]">
        <div className="flex items-center gap-2 px-2 py-1 mb-2">
          <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center text-white text-xs font-semibold shrink-0">
            {user?.name?.[0] ?? '?'}
          </div>
          <div className="min-w-0">
            <p className="text-[var(--text-primary)] text-xs font-medium truncate">{user?.name}</p>
            <p className="text-gray-500 text-xs truncate">{user?.email}</p>
          </div>
        </div>
        <button
          onClick={copyMcpConfig}
          className="w-full text-left text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white text-xs px-2 py-1 rounded transition-colors"
        >
          {mcpCopied ? '✓ コピーしました' : '🔌 MCP接続情報をコピー'}
        </button>
        <button
          onClick={handleLogout}
          className="w-full text-left text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white text-xs px-2 py-1 rounded transition-colors"
        >
          ログアウト
        </button>
      </div>
    </aside>
  )
}
