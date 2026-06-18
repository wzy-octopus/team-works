import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'
import { useAuthStore } from '../stores/authStore'

interface TenantInfo {
  id: string
  name: string
}

export function LoginPage() {
  const navigate = useNavigate()
  const { setUser, setTenantId } = useAuthStore()
  const [step, setStep] = useState<1 | 2>(1)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [tenants, setTenants] = useState<TenantInfo[]>([])

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await api.post('/auth/login', { email, password })
      const { access_token, user, tenants: tenantList } = res.data
      localStorage.setItem('access_token', access_token)
      setUser(user)
      if (tenantList.length === 1) {
        setTenantId(tenantList[0].id)
        navigate('/dashboard')
      } else {
        setTenants(tenantList)
        setStep(2)
      }
    } catch {
      setError('メールアドレスまたはパスワードが正しくありません')
    } finally {
      setLoading(false)
    }
  }

  function handleTenantSelect(id: string) {
    setTenantId(id)
    navigate('/dashboard')
  }

  return (
    <div className="min-h-screen flex bg-[var(--bg-base)]">
      {/* Left branding */}
      <div className="hidden lg:flex w-1/2 bg-gradient-to-br from-indigo-900 to-indigo-700 flex-col justify-center px-16">
        <div className="mb-8">
          <div className="w-12 h-12 rounded-xl bg-white/20 flex items-center justify-center text-2xl font-bold text-white mb-4">
            T
          </div>
          <h1 className="text-4xl font-bold text-white mb-3">TeamWorks</h1>
          <p className="text-indigo-200 text-lg">チームの作業を見える化し、<br />AI時代の新しい協同を実現</p>
        </div>
        <div className="space-y-4">
          {[
            { icon: '✅', title: 'タスクの透明化', desc: 'チーム全員のタスクをリアルタイムで共有' },
            { icon: '🤖', title: 'AI週報', desc: 'AIが自動でサマリを生成し、週報作成を効率化' },
            { icon: '💬', title: 'Slack / Teams 連携', desc: 'チャットから自然言語でタスクを登録' },
          ].map((f) => (
            <div key={f.title} className="flex items-start gap-3">
              <span className="text-xl">{f.icon}</span>
              <div>
                <p className="text-white font-medium">{f.title}</p>
                <p className="text-indigo-200 text-sm">{f.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Right form */}
      <div className="flex-1 flex flex-col justify-center items-center px-8">
        {/* Step indicator */}
        <div className="flex items-center gap-2 mb-8">
          {[1, 2].map((s) => (
            <div key={s} className="flex items-center gap-2">
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                  step > s
                    ? 'bg-green-500 text-white'
                    : step === s
                    ? 'bg-indigo-600 text-white'
                    : 'bg-[var(--bg-hover)] text-gray-400'
                }`}
              >
                {step > s ? '✓' : s}
              </div>
              <span className={`text-xs ${step === s ? 'text-white' : 'text-gray-500'}`}>
                {s === 1 ? '認証' : 'テナント選択'}
              </span>
              {s < 2 && <div className="w-8 h-px bg-white/20" />}
            </div>
          ))}
        </div>

        <div className="w-full max-w-sm">
          {step === 1 ? (
            <>
              <h2 className="text-2xl font-bold text-[var(--text-primary)] mb-2">ログイン</h2>
              <p className="text-gray-400 text-sm mb-6">アカウントにサインインしてください</p>

              <div className="space-y-3 mb-6">
                <button className="w-full flex items-center justify-center gap-3 px-4 py-3 rounded-lg border border-[var(--border)] text-[var(--text-primary)] text-sm hover:bg-[var(--bg-hover)] transition-colors">
                  <img src="https://www.google.com/favicon.ico" className="w-4 h-4" alt="" />
                  Google アカウントでログイン
                </button>
                <button className="w-full flex items-center justify-center gap-3 px-4 py-3 rounded-lg border border-[var(--border)] text-[var(--text-primary)] text-sm hover:bg-[var(--bg-hover)] transition-colors">
                  <span className="text-blue-400 font-bold text-sm">M</span>
                  Microsoft アカウントでログイン
                </button>
              </div>

              <div className="flex items-center gap-3 mb-6">
                <div className="flex-1 h-px bg-[var(--bg-hover)]" />
                <span className="text-gray-500 text-xs">または</span>
                <div className="flex-1 h-px bg-[var(--bg-hover)]" />
              </div>

              <form onSubmit={handleLogin} className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">メールアドレス</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    className="w-full px-3 py-2.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border)] text-[var(--text-primary)] placeholder-gray-500 text-sm focus:outline-none focus:border-indigo-500"
                    placeholder="your@email.com"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">パスワード</label>
                  <div className="relative">
                    <input
                      type={showPw ? 'text' : 'password'}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      className="w-full px-3 py-2.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border)] text-[var(--text-primary)] placeholder-gray-500 text-sm focus:outline-none focus:border-indigo-500 pr-10"
                      placeholder="••••••••"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPw((v) => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                    >
                      {showPw ? '🙈' : '👁'}
                    </button>
                  </div>
                </div>

                {error && (
                  <p className="text-red-400 text-sm bg-red-900/20 border border-red-800 rounded-lg px-3 py-2">
                    {error}
                  </p>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium text-sm transition-colors"
                >
                  {loading ? 'ログイン中...' : 'ログイン'}
                </button>
              </form>
            </>
          ) : (
            <>
              <h2 className="text-2xl font-bold text-[var(--text-primary)] mb-2">ワークスペースを選択</h2>
              <p className="text-gray-400 text-sm mb-6">入室するテナントを選んでください</p>
              <div className="space-y-3">
                {tenants.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => handleTenantSelect(t.id)}
                    className="w-full flex items-center gap-4 px-4 py-4 rounded-xl bg-[var(--bg-input)] border border-[var(--border)] hover:bg-[var(--bg-hover)] hover:border-indigo-500 transition-all text-left"
                  >
                    <div className="w-10 h-10 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold">
                      {t.name[0]}
                    </div>
                    <div>
                      <p className="text-[var(--text-primary)] font-medium">{t.name}</p>
                      <p className="text-gray-400 text-xs">ワークスペースに入る →</p>
                    </div>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
