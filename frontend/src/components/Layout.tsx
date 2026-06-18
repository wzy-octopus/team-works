import { Outlet } from 'react-router-dom'
import { Sidebar } from './Sidebar'
import { useInitUser } from '../hooks/useInitUser'

export function Layout() {
  useInitUser()
  return (
    <div className="flex min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)]">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
