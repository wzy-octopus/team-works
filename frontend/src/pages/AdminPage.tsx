import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import { ThemeToggle } from '../components/ThemeToggle'

interface Member {
  id: string
  user_id: string
  name: string
  email: string
  role: 'admin' | 'manager' | 'member'
  last_login_at: string | null
  manager_user_id: string | null
  project_ids: string[]
}

interface Project {
  id: string
  name: string
  color: string
  description: string | null
  member_count: number
}

const ROLES = ['admin', 'manager', 'member'] as const
const ROLE_LABELS = { admin: '管理者', manager: '上長', member: 'メンバー' }

export function AdminPage() {
  const qc = useQueryClient()
  const [tab, setTab] = useState<'members' | 'projects' | 'roles'>('members')
  const [search, setSearch] = useState('')
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteName, setInviteName] = useState('')
  const [inviteRole, setInviteRole] = useState<'member' | 'manager' | 'admin'>('member')
  const [inviteResult, setInviteResult] = useState<{ message: string; temp_password?: string } | null>(null)
  const [showProjectModal, setShowProjectModal] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [newProjectColor, setNewProjectColor] = useState('#6c63ff')
  const [newProjectDesc, setNewProjectDesc] = useState('')
  const [memberProject, setMemberProject] = useState<Project | null>(null)

  const { data: members = [] } = useQuery<Member[]>({
    queryKey: ['admin-members'],
    queryFn: async () => {
      const res = await api.get('/admin/members')
      return res.data
    },
  })

  const { data: projects = [] } = useQuery<Project[]>({
    queryKey: ['admin-projects'],
    queryFn: async () => {
      const res = await api.get('/admin/projects')
      return res.data
    },
  })

  const inviteMember = useMutation({
    mutationFn: () => api.post('/admin/invite', { email: inviteEmail, role: inviteRole, name: inviteName || undefined }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['admin-members'] })
      setInviteEmail('')
      setInviteName('')
      setInviteResult(res.data)
    },
  })

  const updateMemberRole = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: string }) =>
      api.patch(`/admin/members/${userId}`, { role }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-members'] }),
  })

  const updateManagerAssignment = useMutation({
    mutationFn: ({ userId, managerId }: { userId: string; managerId: string | null }) =>
      api.patch(`/admin/members/${userId}`, managerId
        ? { manager_user_id: managerId }
        : { clear_manager: true }
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-members'] }),
  })

  const createProject = useMutation({
    mutationFn: () =>
      api.post('/admin/projects', {
        name: newProjectName,
        color: newProjectColor,
        description: newProjectDesc || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-projects'] })
      setShowProjectModal(false)
      setNewProjectName('')
      setNewProjectDesc('')
      setNewProjectColor('#6c63ff')
    },
  })

  const deleteMember = useMutation({
    mutationFn: (userId: string) => api.delete(`/admin/members/${userId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-members'] }),
  })

  const addProjectMember = useMutation({
    mutationFn: ({ projectId, userId }: { projectId: string; userId: string }) =>
      api.post(`/admin/projects/${projectId}/members`, null, { params: { user_id: userId } }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-members'] })
      qc.invalidateQueries({ queryKey: ['admin-projects'] })
    },
  })

  const removeProjectMember = useMutation({
    mutationFn: ({ projectId, userId }: { projectId: string; userId: string }) =>
      api.delete(`/admin/projects/${projectId}/members/${userId}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-members'] })
      qc.invalidateQueries({ queryKey: ['admin-projects'] })
    },
  })

  const filteredMembers = members.filter(
    (m) =>
      m.name.toLowerCase().includes(search.toLowerCase()) ||
      m.email.toLowerCase().includes(search.toLowerCase())
  )

  const managers = members.filter((m) => m.role === 'admin' || m.role === 'manager')

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">管理設定</h1>
        <ThemeToggle />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-[var(--bg-hover)] rounded-lg p-1 mb-6 w-fit">
        {(['members', 'projects', 'roles'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-md text-sm transition-colors ${
              tab === t ? 'bg-indigo-600 text-white' : 'text-gray-700 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
            }`}
          >
            {t === 'members' ? 'メンバー管理' : t === 'projects' ? 'プロジェクト管理' : 'ロール・上長設定'}
          </button>
        ))}
      </div>

      {tab === 'members' && (
        <div>
          {/* Search & invite */}
          <div className="flex gap-3 mb-4">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="名前・メールで検索..."
              className="flex-1 px-3 py-2 rounded-lg bg-[var(--bg-input)] border border-[var(--border)] text-[var(--text-primary)] placeholder-gray-500 text-sm focus:outline-none focus:border-indigo-500"
            />
          </div>

          {/* Invite banner */}
          <div className="bg-indigo-900/20 border border-indigo-500/30 rounded-xl p-4 mb-4">
            <div className="flex gap-3 items-end">
              <div className="flex-1">
                <label className="block text-xs text-gray-700 dark:text-gray-400 mb-1">メールアドレス</label>
                <input
                  value={inviteEmail}
                  onChange={(e) => { setInviteEmail(e.target.value); setInviteResult(null) }}
                  placeholder="invite@example.com"
                  type="email"
                  className="w-full px-3 py-2 rounded-lg bg-[var(--bg-input)] border border-[var(--border)] text-[var(--text-primary)] placeholder-gray-500 text-sm focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div className="flex-1">
                <label className="block text-xs text-gray-700 dark:text-gray-400 mb-1">名前（新規ユーザーの場合）</label>
                <input
                  value={inviteName}
                  onChange={(e) => setInviteName(e.target.value)}
                  placeholder="山田 太郎"
                  className="w-full px-3 py-2 rounded-lg bg-[var(--bg-input)] border border-[var(--border)] text-[var(--text-primary)] placeholder-gray-500 text-sm focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div className="w-36">
                <label className="block text-xs text-gray-700 dark:text-gray-400 mb-1">ロール</label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value as typeof inviteRole)}
                  className="w-full px-3 py-2 rounded-lg bg-[var(--bg-surface)] border border-[var(--border)] text-gray-900 dark:text-white text-sm focus:outline-none"
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>{ROLE_LABELS[r]}</option>
                  ))}
                </select>
              </div>
              <button
                onClick={() => inviteMember.mutate()}
                disabled={!inviteEmail || inviteMember.isPending}
                className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium transition-colors"
              >
                追加
              </button>
            </div>
            {inviteResult && (
              <div className={`mt-3 p-3 rounded-lg text-sm ${inviteResult.temp_password ? 'bg-yellow-900/40 border border-yellow-500/40 text-yellow-200' : 'bg-green-900/40 border border-green-500/40 text-green-200'}`}>
                <p>{inviteResult.message}</p>
                {inviteResult.temp_password && (
                  <p className="mt-1 font-mono text-yellow-100">
                    初回ログインパスワード: <span className="font-bold">{inviteResult.temp_password}</span>
                  </p>
                )}
              </div>
            )}
            {inviteMember.isError && (
              <p className="mt-3 text-sm text-red-400">
                {(inviteMember.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? '追加に失敗しました'}
              </p>
            )}
          </div>

          {/* Members table */}
          <div className="bg-[var(--bg-surface)] rounded-xl border border-[var(--border)] overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[var(--border)]">
                  <th className="text-left px-4 py-3 text-gray-600 dark:text-gray-400 text-xs uppercase font-medium">メンバー</th>
                  <th className="text-left px-4 py-3 text-gray-600 dark:text-gray-400 text-xs uppercase font-medium">ロール</th>
                  <th className="text-left px-4 py-3 text-gray-600 dark:text-gray-400 text-xs uppercase font-medium">最終ログイン</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {filteredMembers.map((m) => (
                  <tr key={m.id} className="border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--bg-hover)]">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center text-white text-sm font-medium">
                          {m.name[0]}
                        </div>
                        <div>
                          <p className="text-[var(--text-primary)] text-sm font-medium">{m.name}</p>
                          <p className="text-gray-600 dark:text-gray-500 text-xs">{m.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <select
                        value={m.role}
                        onChange={(e) => updateMemberRole.mutate({ userId: m.user_id, role: e.target.value })}
                        className="bg-[var(--bg-base)] border border-[var(--border)] text-gray-900 dark:text-white text-sm px-2 py-1 rounded focus:outline-none"
                      >
                        {ROLES.map((r) => (
                          <option key={r} value={r}>{ROLE_LABELS[r]}</option>
                        ))}
                      </select>
                    </td>
                    <td className="px-4 py-3 text-gray-700 dark:text-gray-400 text-sm">
                      {m.last_login_at
                        ? new Date(m.last_login_at).toLocaleDateString('ja-JP')
                        : '—'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => deleteMember.mutate(m.user_id)}
                        className="text-gray-600 hover:text-red-400 text-sm transition-colors"
                      >
                        削除
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'projects' && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {projects.map((p) => (
            <div key={p.id} className="bg-[var(--bg-surface)] rounded-xl p-4 border border-[var(--border)]">
              <div className="flex items-center gap-2 mb-3">
                <span className="w-3 h-3 rounded-full" style={{ backgroundColor: p.color }} />
                <h3 className="text-[var(--text-primary)] font-medium">{p.name}</h3>
                <span className="ml-auto text-xs px-2 py-0.5 rounded-full bg-green-900 text-green-300">
                  {p.member_count}名
                </span>
              </div>
              {p.description && <p className="text-gray-700 dark:text-gray-400 text-xs">{p.description}</p>}
              <button
                onClick={() => setMemberProject(p)}
                className="mt-3 w-full py-1.5 rounded-lg border border-[var(--border)] text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white text-xs transition-colors"
              >
                メンバー管理
              </button>
            </div>
          ))}
          <button
            onClick={() => setShowProjectModal(true)}
            className="flex flex-col items-center justify-center gap-2 bg-transparent rounded-xl p-4 border-2 border-dashed border-[var(--border)] text-gray-600 dark:text-gray-500 hover:text-gray-900 dark:hover:text-white hover:border-gray-400 dark:hover:border-white/40 transition-colors min-h-24"
          >
            <span className="text-2xl">+</span>
            <span className="text-sm">新規プロジェクト作成</span>
          </button>
        </div>
      )}

      {tab === 'roles' && (
        <div className="bg-[var(--bg-surface)] rounded-xl border border-[var(--border)] overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[var(--border)]">
                <th className="text-left px-4 py-3 text-gray-600 dark:text-gray-400 text-xs uppercase font-medium">メンバー</th>
                <th className="text-left px-4 py-3 text-gray-600 dark:text-gray-400 text-xs uppercase font-medium">ロール</th>
                <th className="text-left px-4 py-3 text-gray-600 dark:text-gray-400 text-xs uppercase font-medium">週報送付先（上長）</th>
              </tr>
            </thead>
            <tbody>
              {members.filter((m) => m.role === 'member').map((m) => (
                <tr key={m.id} className="border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--bg-hover)]">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center text-white text-xs font-medium">
                        {m.name[0]}
                      </div>
                      <span className="text-[var(--text-primary)] text-sm">{m.name}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="text-xs bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 px-2 py-0.5 rounded-full">
                      {ROLE_LABELS[m.role]}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <select
                      value={m.manager_user_id ?? ''}
                      onChange={(e) =>
                        updateManagerAssignment.mutate({
                          userId: m.user_id,
                          managerId: e.target.value || null,
                        })
                      }
                      className="bg-[var(--bg-base)] border border-[var(--border)] text-gray-900 dark:text-white text-sm px-2 py-1 rounded focus:outline-none"
                    >
                      <option value="">未設定 ⚠</option>
                      {managers.map((mg) => (
                        <option key={mg.id} value={mg.user_id}>{mg.name}</option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Project member management modal */}
      {memberProject && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-[var(--bg-surface)] rounded-2xl p-6 border border-[var(--border)] w-full max-w-lg mx-4 max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-[var(--text-primary)] text-lg font-bold">
                {memberProject.name} のメンバー
              </h3>
              <button
                onClick={() => setMemberProject(null)}
                className="text-gray-500 hover:text-gray-900 dark:hover:text-white"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-gray-600 dark:text-gray-400 mb-2 uppercase tracking-wider">所属メンバー</p>
            <div className="space-y-2 mb-5">
              {members.filter((m) => m.project_ids.includes(memberProject.id)).length === 0 ? (
                <p className="text-gray-600 dark:text-gray-500 text-sm">まだメンバーが割り当てられていません</p>
              ) : (
                members
                  .filter((m) => m.project_ids.includes(memberProject.id))
                  .map((m) => (
                    <div
                      key={m.user_id}
                      className="flex items-center gap-3 bg-[var(--bg-base)] rounded-lg px-3 py-2 border border-[var(--border-subtle)]"
                    >
                      <div className="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center text-white text-xs font-medium">
                        {m.name[0]}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-[var(--text-primary)] text-sm truncate">{m.name}</p>
                        <p className="text-gray-600 dark:text-gray-500 text-xs truncate">{m.email}</p>
                      </div>
                      <button
                        onClick={() =>
                          removeProjectMember.mutate({ projectId: memberProject.id, userId: m.user_id })
                        }
                        disabled={removeProjectMember.isPending}
                        className="text-gray-600 hover:text-red-400 disabled:opacity-50 text-sm"
                      >
                        除外
                      </button>
                    </div>
                  ))
              )}
            </div>

            <p className="text-xs text-gray-600 dark:text-gray-400 mb-2 uppercase tracking-wider">追加できるメンバー</p>
            <div className="space-y-2">
              {members.filter((m) => !m.project_ids.includes(memberProject.id)).length === 0 ? (
                <p className="text-gray-600 dark:text-gray-500 text-sm">全員が所属しています</p>
              ) : (
                members
                  .filter((m) => !m.project_ids.includes(memberProject.id))
                  .map((m) => (
                    <div
                      key={m.user_id}
                      className="flex items-center gap-3 bg-[var(--bg-base)] rounded-lg px-3 py-2 border border-[var(--border-subtle)]"
                    >
                      <div className="w-7 h-7 rounded-full bg-gray-500 flex items-center justify-center text-white text-xs font-medium">
                        {m.name[0]}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-[var(--text-primary)] text-sm truncate">{m.name}</p>
                        <p className="text-gray-600 dark:text-gray-500 text-xs truncate">{m.email}</p>
                      </div>
                      <button
                        onClick={() =>
                          addProjectMember.mutate({ projectId: memberProject.id, userId: m.user_id })
                        }
                        disabled={addProjectMember.isPending}
                        className="text-indigo-500 hover:text-indigo-400 disabled:opacity-50 text-sm font-medium"
                      >
                        追加
                      </button>
                    </div>
                  ))
              )}
            </div>

            <button
              onClick={() => setMemberProject(null)}
              className="mt-6 w-full py-2 rounded-lg border border-[var(--border)] text-gray-700 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white text-sm"
            >
              閉じる
            </button>
          </div>
        </div>
      )}

      {/* New project modal */}
      {showProjectModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-[var(--bg-surface)] rounded-2xl p-6 border border-[var(--border)] w-full max-w-md mx-4">
            <h3 className="text-[var(--text-primary)] text-lg font-bold mb-4">新規プロジェクト作成</h3>
            <div className="space-y-3 mb-4">
              <div>
                <label className="block text-xs text-gray-700 dark:text-gray-400 mb-1">プロジェクト名</label>
                <input
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  placeholder="プロジェクト名"
                  className="w-full px-3 py-2 rounded-lg bg-[var(--bg-input)] border border-[var(--border)] text-[var(--text-primary)] placeholder-gray-500 text-sm focus:outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-700 dark:text-gray-400 mb-1">カラー</label>
                <div className="flex items-center gap-3">
                  <input
                    type="color"
                    value={newProjectColor}
                    onChange={(e) => setNewProjectColor(e.target.value)}
                    className="w-10 h-10 rounded cursor-pointer bg-transparent border-0"
                  />
                  <span className="text-gray-900 dark:text-white text-sm font-mono">{newProjectColor}</span>
                </div>
              </div>
              <div>
                <label className="block text-xs text-gray-700 dark:text-gray-400 mb-1">説明（任意）</label>
                <textarea
                  value={newProjectDesc}
                  onChange={(e) => setNewProjectDesc(e.target.value)}
                  rows={2}
                  className="w-full px-3 py-2 rounded-lg bg-[var(--bg-input)] border border-[var(--border)] text-[var(--text-primary)] placeholder-gray-500 text-sm focus:outline-none focus:border-indigo-500 resize-none"
                />
              </div>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setShowProjectModal(false)}
                className="flex-1 py-2 rounded-lg border border-[var(--border)] text-gray-700 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white text-sm"
              >
                キャンセル
              </button>
              <button
                onClick={() => createProject.mutate()}
                disabled={!newProjectName || createProject.isPending}
                className="flex-1 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium"
              >
                作成
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
